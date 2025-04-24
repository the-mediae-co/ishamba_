import json
from datetime import datetime, time
from typing import Any
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from django.forms.models import inlineformset_factory
from django.http import (HttpRequest, HttpResponse, HttpResponseRedirect,
                         JsonResponse)
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic import (CreateView, DeleteView, DetailView, FormView,
                                  ListView, UpdateView)

import django_filters
from actstream.models import Action
from dateutil import parser, tz
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView
from django_tables2.export.views import ExportMixin

from agri.constants import SUBSCRIPTION_FLAG
from agri.models import Commodity
from callcenters.models import CallCenterOperator
from calls.models import Call
from core.utils.functional import is_jquery_ajax
from customers.constants import JOIN_METHODS, STOP_METHODS
from customers.forms import (AddCommodityForm, CropHistoryItemForm,
                             CustomerForm, CustomerListFilterForm,
                             CustomerMarketForm, CustomerMarketFormSetHelper,
                             CustomerQuestionAnswerForm,
                             CustomerQuestionAnswerFormset,
                             CustomerQuestionAnswerFormSetHelper,
                             MarketSubscriptionForm, TipSeriesSubscriptionForm)
from customers.models import (CropHistory, Customer, CustomerCommodity,
                              CustomerPhone, CustomerQuestionAnswer)
from customers.tables import (CallHistoryTable, CommodityTable,
                              CropHistoryTable, CustomerTable,
                              IncomingSMSTable, MarketSubscriptionTable,
                              OutgoingSMSTable, SubscriptionHistoryTable,
                              TipSentTable, TipSeriesSubscriptionTable)
from customers.tasks import send_customers_email_via_celery
from markets.models import MarketSubscription
from sms import utils as sms_utils
from sms.constants import OUTGOING_SMS_TYPE
from sms.forms import SingleOutgoingSMSForm
from sms.models import IncomingSMS, OutgoingSMS, SMSRecipient
from sms.tasks import send_message
from subscriptions.models import Subscription
from tips.models import TipSent, TipSeriesSubscription
from world.models import Border, BorderLevelName
from world.utils import get_country_for_phone, process_border_ajax_menus


class CustomerListView(ExportMixin, SingleTableView):

    model = Customer
    table_class = CustomerTable
    form_class = CustomerListFilterForm
    # pagination_class = LazyPaginator  # Performance improvement, preventing a count of all customers
    paginate_by = 25
    export_name = 'Exported Customers'
    export_formats = ['csv', 'xls']
    exclude_columns = ["bulk", "location", "edit"]

    def get_queryset(self):
        self.form = self.form_class(self.request.GET)
        queryset = super().get_queryset().order_by('id')  # Customer class does not have a default sort order set, and without it, pagination may do strange things
        # 'customer_id', 'name', 'phone', 'sex', 'border0', 'border1', 'categories', 'last_editor', 'join_method',
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()

        current_call_center = CallCenterOperator.objects.filter(operator=user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            border_query = f'border{current_call_center.border_level}'
            queryset = queryset.filter(phones__isnull=False, **{border_query: current_call_center.border_id})
        else:
            return queryset.none()

        if self.form.is_valid():
            customer_id = self.form.cleaned_data.get('customer_id')
            if customer_id:
                queryset = queryset.filter(id=customer_id)

            name = self.form.cleaned_data.get('name')
            if name:
                queryset = queryset.filter(name__icontains=name)

            phone = self.form.cleaned_data.get('phone')
            if phone:
                queryset = queryset.filter(phones__number__contains=phone)

            sex = self.form.cleaned_data.get('sex')
            if sex:
                queryset = queryset.filter(sex__iexact=sex)  # The production DB has both upper and lower case

            border0s = self.form.cleaned_data.get('border0')
            if border0s:
                queryset = queryset.filter(border0__pk__in=border0s)

            border1s = self.form.cleaned_data.get('border1')
            if border1s:
                queryset = queryset.filter(border1__pk__in=border1s)

            categories = self.form.cleaned_data.get('categories')
            if categories:
                queryset = queryset.filter(categories__in=categories)

            created_from = self.form.cleaned_data.get('created_from')
            if created_from:
                queryset = queryset.filter(created__gte=created_from)

            created_to = self.form.cleaned_data.get('created_to')
            if created_to:
                queryset = queryset.filter(created__lte=created_to)

            complete_location = self.form.cleaned_data.get('complete_location')
            if complete_location and complete_location != "ALL":
                if complete_location == "Yes":
                    queryset = queryset.filter(border3__isnull=False,
                                               border2__isnull=False,
                                               border1__isnull=False,
                                               border0__isnull=False,)
                elif complete_location == "No":
                    queryset = queryset.exclude(border3__isnull=False,
                                                border2__isnull=False,
                                                border1__isnull=False,
                                                border0__isnull=False,)

            has_gender = self.form.cleaned_data.get('has_gender')
            if has_gender and has_gender != "ALL":
                if has_gender == "Yes":
                    queryset = queryset.filter(sex__gt='')
                elif has_gender == "No":
                    queryset = queryset.exclude(sex__gt='')

            last_editor = self.form.cleaned_data.get('last_editor')
            if last_editor:
                queryset = queryset.filter(last_editor_id__in=last_editor)

            join_method = self.form.cleaned_data.get('join_method')
            if join_method:
                queryset = queryset.filter(join_method=join_method)

            stop_method = self.form.cleaned_data.get('stop_method')
            if stop_method:
                queryset = queryset.filter(stop_method=stop_method)

        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtered'] = self.form.data or False
        page = self.request.GET.get('page', 1)

        if 'paginator' in ctx and ctx['paginator'] is not None:
            paginator = ctx['paginator']
            ctx['record_count'] = paginator.count
            if 'table' in ctx and ctx['table'] is not None:
                table = ctx['table']
                table.page_range = paginator.get_elided_page_range(number=page)
        else:
            ctx['record_count'] = self.get_queryset().count()

        selected_customers = self.request.session.get('selected_customers', [])
        ctx['selected_customers'] = selected_customers
        ctx['selected_customers_count'] = len(selected_customers)

        export_fields = []
        for key in self.table_class.base_columns.keys():
            if key in self.table_class.Meta.fields and key not in self.exclude_columns:
                title = self.table_class.base_columns[key].header
                if not title:
                    title = key.title()
                export_fields.append({'key': key, 'title': title})
        ctx['export_fields'] = export_fields
        return ctx

    def get(self, request, *args, **kwargs):
        # If a jquery ajax request, handle it differently
        if is_jquery_ajax(self.request):
            selected_border0s = request.GET.getlist('border0', [])
            selected_border1s = request.GET.getlist('border1', [])
            selected_border2s = request.GET.getlist('border2', [])
            selected_border3s = request.GET.getlist('border3', [])
            response = process_border_ajax_menus(selected_border0s, selected_border1s,
                                                 selected_border2s, selected_border3s, self.request.POST.dict())
            return JsonResponse(response)

        if 'HTTP_REFERER' in request.META:
            r = urlparse(request.META['HTTP_REFERER'])
            # If this is not a request for another paginated page, then clear the session selected Customers data
            if r.netloc != request.get_host() or r.path != request.path:
                if 'selected_customers' in request.session:
                    del request.session['selected_customers']
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # If a jquery ajax request
        if is_jquery_ajax(self.request):
            if 'export-customers' in request.POST:
                fields = dict(request.POST)
                fields.pop('csrfmiddlewaretoken', None)
                fields.pop('export-customers', None)
                export_format = fields.pop('export-format', 'csv')
                if isinstance(export_format, list):
                    export_format = export_format[0]
                selected_customers = request.session.get('selected_customers', [])
                # Spawn a celery task to generate and email this export
                send_customers_email_via_celery.delay(request.user.email, selected_customers, list(fields.keys()), export_format)
                response = JsonResponse({'success': True, 'user_email': request.user.email})
                return response
            else:
                # Update user session with the selected customers so that the selection persists across pages
                customers = json.loads(request.body)
                if customers is None:
                    selected_customers = []
                elif customers == 'all':
                    # Get list of all filtered customers (as strings)
                    selected_customers = list(map(str, self.get_queryset().values_list('id', flat=True)))
                else:
                    selected_customers = request.session.get('selected_customers', [])
                    for t in customers:
                        if t and customers[t] and t not in selected_customers:
                            selected_customers.append(t)
                        elif t and not customers[t] and t in selected_customers:
                            selected_customers.remove(t)

                self.request.session['selected_customers'] = selected_customers
                response_data = {
                    'customers_selected_count': len(selected_customers)
                }
                response = JsonResponse(response_data)
                return response

        # Not an ajax post
        self.object_list = self.get_queryset()
        ctx = self.get_context_data(**kwargs)
        # Get the Customer IDs from the session, otherwise the form submission
        customer_ids = request.session.get('selected_customers', request.POST.getlist('bulk-customers'))

        if 'bulk-sms' in request.POST:
            # The user submitted the bulk sms form.
            # apply network filters so that the customer count in the sms compose will be correct
            customers = Customer.objects.filter(pk__in=customer_ids, has_requested_stop=False)

            # Convert the filtered list back into a list of pk's
            customer_ids = list(customers.values_list('pk', flat=True))

            # Pack the session data, similar to how CustomerFilterFormView would
            self.request.session['bulk_customer'] = {
                'customer_ids': customer_ids,
                'form_data': customer_ids,
                'count': len(customer_ids),
                # Override the default customer view success url, to return to the customers view
                'success_url': 'customers:customer_list'
            }

            # The user took action on their selections so clear them from the session
            if 'selected_customers' in request.session:
                del request.session['selected_customers']

            next_url = reverse_lazy('core_management_customer_bulk_compose')
            return HttpResponseRedirect(next_url)
        else:
            # We want exports to come as POST requests to keep the URL params clean. However,
            # exports expects them to come via GET, so we need to move some params to make that work.
            if self.export_trigger_param not in request.GET:
                request.GET._mutable = True
                export_format = request.POST.get('export-action', 'export-csv').split('-')[-1]
                request.GET.update({self.export_trigger_param: export_format})
                request.GET._mutable = False

            # Set the object_list to be only the selected tasks
            self.object_list = Customer.objects.filter(pk__in=customer_ids)

            # The export action does not redirect nor refresh the current page,
            # so don't reset the selected_customers session data as this will confuse the user.
            # if 'selected_customers' in self.request.session:
            #     del self.request.session['selected_customers']

            # Now generate the export
            return super().render_to_response(ctx, **kwargs)


def _get_customer_context_data(customer: Customer) -> dict:
    context_data = {}
    if customer and not customer.border0:
        if any([customer.border1, customer.border2, customer.border3]):
            # Set the customer's other administrative boundaries based on what we have
            if customer.border3 and not customer.border2:
                customer.border2 = customer.border3.parent
            if customer.border2 and not customer.border1:
                customer.border1 = customer.border2.parent
            if customer.border1 and not customer.border0:
                customer.border0 = customer.border1.parent
        elif customer.main_phone:
            # Guess the customer's country (border0) by their phone number
            try:
                country = get_country_for_phone(customer.main_phone)
                customer.border0 = country
            except ValueError:
                # If not a country that we operate in, skip the country check/save
                return context_data

        customer.save(update_fields=['border0', 'border1', 'border2', 'border3'])

    if customer.border0:
        # Set the border level names, even if we don't know the customer's other location details
        b2_label = BorderLevelName.objects.get(country=customer.border0, level=2).name
        b3_label = BorderLevelName.objects.get(country=customer.border0, level=3).name
    else:
        # Default to Kenya
        b2_label = 'Subcounty'
        b3_label = 'Ward'
    context_data.update({
        'border2_label': b2_label,
        'border3_label': b3_label,
    })

    if customer.location:
        gps_string = dict(zip(('lng', 'lat'), customer.location.coords))
        context_data.update({'customerGPS': json.dumps(gps_string)})
    elif customer.border3:
        gps_string = dict(zip(('lng', 'lat'), customer.border3.border.centroid))
        context_data.update({'customerGPS': json.dumps(gps_string)})
    else:
        context_data.update({'customerGPS': None})

    if customer.border3:
        # Add the geometry (multipolygon) of the border3 for drawing on a leaflet map
        b2 = customer.border2
        context_data.update({
            'border2_name': b2.name,
            'border2_label': b2_label,
            'border2_geom': b2.border.json,
            'border2_centroid': b2.border.centroid.json,
        })
        b3 = customer.border3
        context_data.update({
            'border3_name': b3.name,
            'border3_label': b3_label,
            'border3_geom': b3.border.json,
            'border3_centroid': b3.border.centroid.json,
        })
    else:
        context_data.update({
            'border2_name': None,
            'border2_label': b2_label,
            'border2_geom': None,
            'border2_centroid': None,
        })
        context_data.update({
            'border3_name': None,
            'border3_label': b3_label,
            'border3_geom': None,
            'border3_centroid': None,
        })
    return context_data


class CustomerDetailView(DetailView):

    model = Customer

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        customer = context_data.get('customer')
        context_data.update(_get_customer_context_data(customer))
        context_data.update({'enableLeafletEditing': False})
        return context_data


class CustomerEditMixin(object):

    model = Customer
    form_class = None  # Constructed dynamically in get_form()

    def get_markets_formset(self, post=None):
        formset = inlineformset_factory(Customer,
                                        MarketSubscription,
                                        form=CustomerMarketForm,
                                        extra=1)
        return formset(post, instance=self.object)

    def get_questions_formset(self, post=None):
        formset = inlineformset_factory(Customer,
                                        CustomerQuestionAnswer,
                                        form=CustomerQuestionAnswerForm,
                                        formset=CustomerQuestionAnswerFormset)
        return formset(post, instance=self.object)

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        if self.object:
            # If we have the customer object, set the initial
            # value of the phones field to their list of numbers
            customer = self.object
            numbers = customer.phones.order_by('-is_main', 'number').values_list('number', flat=True)
            initial.update({
                'phones': ','.join(numbers)
            })
        return initial

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        customer = self.object
        context_data.update(_get_customer_context_data(customer))
        context_data.update({'enableLeafletEditing': True})
        return context_data

    def form_invalid(self, form, markets_form, questions_form):
        markets_form_helper = CustomerMarketFormSetHelper()
        questions_form_helper = CustomerQuestionAnswerFormSetHelper()
        return self.render_to_response(
            self.get_context_data(form=form,
                                  markets_form=markets_form,
                                  markets_form_helper=markets_form_helper,
                                  questions_form=questions_form,
                                  questions_form_helper=questions_form_helper))

    def get_form(self, form_class=None):
        """Return an instance of the form to be used in this view."""
        # Default to Kenya administrative border names
        border_names = {
            'border0': _('Country'),
            'border1': _('County'),
            'border2': _('Subcounty'),
            'border3': _('Ward'),
        }
        customer = self.object
        # If the customer has a country set, use the names of that country
        if customer and customer.border0:
            for level in range(1, 4):
                border_names.update({
                    f'border{level}': BorderLevelName.objects.get(country=customer.border0, level=level).name,
                })
        return CustomerForm(border_names, **self.get_form_kwargs())

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        markets_form = self.get_markets_formset()
        markets_form_helper = CustomerMarketFormSetHelper()
        questions_form = self.get_questions_formset()
        questions_form_helper = CustomerQuestionAnswerFormSetHelper()
        context_data = self.get_context_data(form=form,
                                  markets_form=markets_form,
                                  markets_form_helper=markets_form_helper,
                                  questions_form=questions_form,
                                  questions_form_helper=questions_form_helper)
        return self.render_to_response(context_data)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        # If a jquery ajax request, handle it differently
        if is_jquery_ajax(self.request):
            if not hasattr(form, 'cleaned_data'):
                # We don't need full form validation, only cleaned data
                form.full_clean()
            if hasattr(form, 'cleaned_data'):
                # If there were no errors in cleaning
                selected_border0 = form.cleaned_data.get('border0', [1])
                if not selected_border0:
                    # For now, if there was no selection, we assume Kenya since that's the majority of customers
                    selected_border0 = Border.objects.get(country='Kenya', level=0)
                selected_border1 = form.cleaned_data.get('border1', [])
                selected_border2 = form.cleaned_data.get('border2', [])
                selected_border3 = form.cleaned_data.get('border3', [])
                response = process_border_ajax_menus(selected_border0, selected_border1,
                                                     selected_border2, selected_border3, self.request.POST.dict())
                if response['selected_border3s']:
                    # Add the geometry (multipolygon) of the border3 for drawing on a leaflet map
                    b3_id = response['selected_border3s'][0]
                    b3 = Border.objects.get(id=b3_id)
                    response.update({'border3_name': b3.name})
                    response.update({'border3_label': response['border3_label']})
                    response.update({'border3_geom': b3.border.json})
                    response.update({'border3_centroid': b3.border.centroid.json})
                if response['selected_border2s']:
                    b2_id = response['selected_border2s'][0]
                    b2 = Border.objects.get(id=b2_id)
                    response.update({'border2_name': b2.name})
                    response.update({'border2_label': response['border2_label']})
                    response.update({'border2_geom': b2.border.json})
                    response.update({'border2_centroid': b2.border.centroid.json})
            else:
                response = {}
            return JsonResponse(response)

        markets_form = self.get_markets_formset(self.request.POST)
        questions_form = self.get_questions_formset(self.request.POST)
        if form.is_valid() and markets_form.is_valid() and questions_form.is_valid():
            return self.form_valid(form, markets_form, questions_form)
        else:
            return self.form_invalid(form, markets_form, questions_form)

    def form_valid(self, form, markets_form, questions_form):
        """
        Parses and tidy's the customer-specific data from the form
        """
        self.object = form.save()  # Customer

        # Gather customer record fields that need updating in the db
        needs_updating = []

        if 'phones' in form.cleaned_data:
            form_phones = form.cleaned_data.get('phones')
            old_phones = set(self.object.phones.all().values_list('number', flat=True))
            new_phones = set(form_phones)
            removed_phones = old_phones - new_phones
            added_phones = new_phones - old_phones
            deleted_phones = self.object.phones.filter(number__in=removed_phones)
            deleted_phones.delete()
            for p in added_phones:
                CustomerPhone.objects.create(number=p, customer=self.object)

            # If at least one phone number was provided
            if len(form_phones) > 0:
                # reset all is_main values
                self.object.phones.filter(is_main=True).update(is_main=False)
                # Set the first number in the list as this customer's main number
                CustomerPhone.objects.filter(number=form_phones[0]).update(is_main=True)

        # If the staff set the has_requested_stop field, record this fact in the customer record
        if 'has_requested_stop' in form.changed_data and form.cleaned_data.get('has_requested_stop'):
            self.object.stop_method = STOP_METHODS.STAFF
            self.object.stop_date = timezone.now().date()
            needs_updating.append('stop_method')
            needs_updating.append('stop_date')
        # If the staff set the border2 and/or border3 field, set the gps location accordingly
        if 'border2' in form.changed_data or 'border3' in form.changed_data:
            # If we have a border3, use it. Otherwise use the border2.
            if 'border3' in form.cleaned_data and form.cleaned_data.get('border3'):
                self.object.location = self.object.border3.border.centroid
            elif 'border2' in form.cleaned_data and form.cleaned_data.get('border2'):
                self.object.location = self.object.border2.border.centroid
            else:
                self.object.location = None
            needs_updating.append('location')
        if len(needs_updating) > 0:
            self.object.save(update_fields=needs_updating)
        markets_form.instance = self.object
        markets_form.save()
        questions_form.instance = self.object
        questions_form.save()
        return HttpResponseRedirect(self.get_success_url())


class CustomerCreateView(CustomerEditMixin, SuccessMessageMixin, CreateView):

    success_message = "%(name)s was created successfully"

    def get_object(self):
        return None

    def form_valid(self, form, markets_form, questions_form):
        """ Extracts the phones from the form. Sends a welcome SMS if the Customer creation is successful. """
        redirect = super().form_valid(form, markets_form, questions_form)
        customer = self.object
        customer.join_method = JOIN_METHODS.STAFF
        customer.save(update_fields=['join_method'])
        # If we don't have the customer's name or location, ask them
        # to start a USSD session to collect their basic information
        if customer.name is None or len(customer.name) == 0 or customer.location is None:
            message, sender, create_task = sms_utils.get_populated_sms_templates_text_and_task(settings.SMS_JOIN,
                                                                                               customer=customer)
            sms = OutgoingSMS.objects.create(text=message,
                                             message_type=OUTGOING_SMS_TYPE.NEW_CUSTOMER_RESPONSE)
            send_message.delay(sms.id, [customer.id], sender=sender, allow_international=True)
        else:
            customer.send_welcome_sms()
        messages.success(self.request, _("Welcome SMS Sent"))
        return redirect

    def get_success_url(self):
        return reverse('customers:customer_detail', args=(self.object.pk,))


class CustomerUpdateView(CustomerEditMixin, SuccessMessageMixin, UpdateView):

    success_message = "%(name)s was updated successfully"

    def get_success_url(self):
        return reverse('customers:customer_detail', args=(self.object.pk,))

    def get(self, request, *args, **kwargs):
        # Calls the CustomerEditMixin to create the form
        return super().get(request, *args, **kwargs)

    def form_valid(self, form, markets_form, questions_form):
        # The CustomerEditMixin takes care of updating the stop_method and stop_date
        redirect = super().form_valid(form, markets_form, questions_form)
        return redirect


class CustomerCallHistoryView(SingleTableView):

    template_name = 'customers/call_history.html'
    model = Call
    table_class = CallHistoryTable

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        queryset = super().get_queryset(**kwargs)
        return queryset.filter(customer=self.customer)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context


class CustomerSubscriptionHistoryView(SingleTableView):

    model = Subscription
    table_class = SubscriptionHistoryTable

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        queryset = super().get_queryset(**kwargs)
        return queryset.filter(customer=self.customer)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context


class CustomerCropHistoryListView(SingleTableView):

    model = CropHistory
    table_class = CropHistoryTable

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        queryset = super().get_queryset(**kwargs)
        return queryset.filter(customer=self.customer)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context


class CustomerCropHistoryUpdateView(SuccessMessageMixin, UpdateView):

    model = CropHistory
    form_class = CropHistoryItemForm
    success_message = "%(customer)s crop history was updated successfully"

    def get_success_url(self):
        return reverse('customers:customer_crop_history_list',
                       kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.object.customer
        return context


class CustomerCropHistoryCreateView(SuccessMessageMixin, CreateView):

    model = CropHistory
    form_class = CropHistoryItemForm
    success_message = "%(customer)s crop history item was created successfully"

    def get_initial(self, *args, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        initial = super().get_initial(*args, **kwargs)
        initial['customer'] = self.customer
        return initial

    def form_valid(self, form):
        # subscriber is a hidden field; ensure it hasn't been altered in POST
        form.instance.customer = self.customer
        form.instance.creator_id = self.request.user.id
        self.object = form.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('customers:customer_crop_history_list',
                       kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context


class CustomerCropHistoryDeleteView(SuccessMessageMixin, DeleteView):

    model = CropHistory
    success_message = "Crop history item was deleted successfully"

    def get_success_url(self):
        return reverse('customers:customer_crop_history_list',
                       kwargs={'pk': self.object.customer.pk})


class CustomerCommodityListView(SingleTableView):
    model = Commodity
    table_class = CommodityTable
    template_name = 'customers/commodity_list.html'

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        return self.customer.commodities.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context

    def get_table_kwargs(self):
        kwargs = super().get_table_kwargs()
        kwargs.update({
            'customer': self.customer
        })
        return kwargs


class CustomerCommodityRemoveView(SuccessMessageMixin, DeleteView):
    model = Commodity
    success_message = "%(commodity)s was removed"
    http_method_names = ['post', 'options', ]

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['c_pk'])
        return self.customer.commodities.all()

    def get_success_url(self):
        return reverse('customers:customer_commodity_list',
                       kwargs={'pk': self.customer.pk})

    def form_valid(self, form):
        tip_subscribed = self.customer.tip_subscriptions.filter(ended=False, series__commodity=self.object).exists()
        if tip_subscribed:
            # This should not happen unless someone is hacking our form submission
            form.add_error(
                field=None,  # Form error, not specific to a field
                error=ValidationError(f"You cannot remove the commodity of an active tip series subscription"))
        market_subscribed = self.customer.market_subscriptions.filter(commodity=self.object).exists()
        if market_subscribed:
            # This should not happen unless someone is hacking our form submission
            form.add_error(
                field=None,  # Form error, not specific to a field
                error=ValidationError(f"You cannot remove the commodity of an active market price subscription"))
        if form.errors:
            return HttpResponseRedirect(self.get_success_url())

        self.customer.commodities.remove(self.object)
        # Copy the logic in parent class rather than calling super()
        # because super() deletes the commodity object. We just want
        # to remove it from this customer.
        success_message = self.get_success_message({'commodity': self.object.name})
        if success_message:
            messages.success(self.request, success_message)
        return HttpResponseRedirect(self.get_success_url())


class CustomerCommodityAddView(SuccessMessageMixin, FormView):
    form_class = AddCommodityForm
    success_message = "%(commodity)s was added"
    template_name = "customers/commodity_form.html"

    def get_success_url(self):
        return reverse(
            "customers:customer_commodity_list",
            kwargs={"pk": self.customer.pk},
        )

    def get_initial(self, *args, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs["pk"])
        initial = super().get_initial(*args, **kwargs)
        initial["customer"] = self.customer
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer"] = self.customer
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if 'instance' in kwargs and kwargs['instance'] is None and self.customer:
            kwargs.update({'instance': self.customer})
        return kwargs

    def form_valid(self, form):
        subscription_flag = form.cleaned_data.get('subscription_flag')
        commodity = form.cleaned_data['commodity']
        cus_cat, created = CustomerCommodity.objects.update_or_create(
            customer=self.customer,
            commodity=commodity,
            defaults={'subscription_flag': subscription_flag}
        )
        if subscription_flag == SUBSCRIPTION_FLAG.FREEMIUM:
            CustomerCommodity.objects.filter(
                customer=self.customer,
                commodity=commodity,
                subscription_flag=subscription_flag
            ).exclude(id=cus_cat.id).update(subscription_flag=None)
        Customer.index_one(self.customer)
        return super().form_valid(form)


class CustomerTipSubscriptionListView(SingleTableView):

    model = CustomerCommodity
    table_class = TipSeriesSubscriptionTable
    template_name = 'customers/tipseriessubscription_list.html'

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        queryset = super().get_queryset(**kwargs)
        return queryset.filter(customer=self.customer)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        context['can_add'] = self.customer.can_add_tipsubscription()
        return context


class CustomerTipSubscriptionUpdateView(SuccessMessageMixin, UpdateView):

    model = TipSeriesSubscription
    form_class = TipSeriesSubscriptionForm
    success_message = "%(series)s subscription was updated successfully"
    template_name = "customers/tipseriessubscription_form.html"

    def get_success_url(self):
        return reverse(
            "customers:customer_tip_subscription_list",
            kwargs={"pk": self.object.customer.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.object.customer
        return context


class CustomerTipSubscriptionDeleteView(SuccessMessageMixin, DeleteView):

    model = TipSeriesSubscription
    http_method_names = ['post', 'options', ]

    def get_object(self, *args, **kwargs):
        subscription = super().get_object(*args, **kwargs)

        # Added so that it can be used in the tip unsubscription action record
        subscription.last_editor_id = self.request.user.id
        return subscription

    def get_success_url(self):
        return reverse('customers:customer_tip_subscription_list',
                       kwargs={'pk': self.object.customer.pk})

    def get_success_message(self, cleaned_data):
        if self.object and self.object.series:
            return _("%(series)s subscription was deleted successfully" % {'series': self.object.series.name})
        else:
            return _("Tip series subscription was deleted successfully")


class CustomerTipSubscriptionCreateView(SuccessMessageMixin, CreateView):

    model = TipSeriesSubscription
    form_class = TipSeriesSubscriptionForm
    success_message = "%(series)s subscription was created successfully"
    template_name = "customers/tipseriessubscription_form.html"

    def get_success_url(self):
        return reverse(
            "customers:customer_tip_subscription_list",
            kwargs={"pk": self.object.customer.pk},
        )

    def get_initial(self, *args, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs["pk"])
        initial = super().get_initial(*args, **kwargs)
        initial["customer"] = self.customer
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer"] = self.customer
        return context

    def form_valid(self, form):
        # customer is a hidden field; ensure it hasn't been altered in POST.
        form.instance.customer = self.customer
        form.instance.creator_id = self.request.user.id
        tss = self.object = form.save()

        return super().form_valid(form)


class MarketSubscriptionListView(SingleTableView):

    model = MarketSubscription
    table_class = MarketSubscriptionTable
    template_name = 'customers/marketpricesubscription_list.html'

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        queryset = super().get_queryset(**kwargs)
        return queryset.filter(customer=self.customer)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        context['can_add'] = self.customer.can_add_marketsubscription()
        return context


class MarketSubscriptionUpdateView(SuccessMessageMixin, UpdateView):

    model = MarketSubscription
    form_class = MarketSubscriptionForm
    template_name = 'customers/marketpricesubscription_form.html'
    success_message = "%(market)s subscription was updated successfully"

    def get_success_url(self):
        return reverse('customers:customer_market_subscription_list',
                       kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.object.customer
        return context

    def form_valid(self, form):
        # Ensure that commodities are added to the customer.commodities set
        customer = form.cleaned_data['customer']
        customer.commodities.add(form.cleaned_data['commodity'])
        return super().form_valid(form)


class MarketSubscriptionCreateView(SuccessMessageMixin, CreateView):

    model = MarketSubscription
    form_class = MarketSubscriptionForm
    template_name = 'customers/marketpricesubscription_form.html'
    success_message = "%(market)s subscription was created successfully"

    def get_initial(self, *args, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        initial = super().get_initial(*args, **kwargs)
        initial['customer'] = self.customer
        return initial

    def form_valid(self, form):
        # customer is a hidden field; ensure it hasn't been altered in POST
        form.instance.customer = self.customer
        form.instance.creator_id = self.request.user.id
        self.object = form.save()
        self.customer.commodities.add(self.object.commodity)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('customers:customer_market_subscription_list',
                       kwargs={'pk': self.object.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context


class MarketSubscriptionDeleteView(SuccessMessageMixin, DeleteView):

    http_method_names = ['post', 'options', ]
    model = MarketSubscription

    def get_object(self, *args, **kwargs):
        subscription = super().get_object(*args, **kwargs)
        # this is only added so that it can be used in the commodity unsubscription
        # action record
        subscription.last_editor_id = self.request.user.id
        return subscription

    def get_success_url(self):
        return reverse('customers:customer_market_subscription_list',
                       kwargs={'pk': self.object.customer.pk})

    def get_success_message(self, cleaned_data):
        if self.object and self.object.market:
            return _("%(market)s subscription was deleted successfully" % {'market': self.object.market.name})
        else:
            return _("Market subscription was deleted successfully")


class IncomingSMSListView(SingleTableView):

    table_class = IncomingSMSTable
    model = IncomingSMS
    view_title = "Incoming"
    url_name = "customers:customer_incoming_sms_history"
    template_name = 'customers/outgoingsms_list.html'

    def get_queryset(self, **kwargs):
        """ Not a BaseSentSMS-derived model: do it differently.
        """
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        return self.customer.incomingsms_set.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        context['title'] = self.view_title
        context['url_name'] = self.url_name
        context['breadcrumb_text'] = self.breadcrumb_text
        return context

    @property
    def breadcrumb_text(self):
        return mark_safe("{} SMS History".format(self.view_title))


class OutgoingSMSFilter(django_filters.FilterSet):
    time_sent_min = django_filters.DateFilter(label=_('From date'),
                                              field_name='time_sent',
                                              widget=forms.DateInput(attrs={'type': 'date',
                                                                            'class': 'form-control'}))
    time_sent_max = django_filters.DateFilter(label=_('To date'),
                                              field_name='time_sent',
                                              widget=forms.DateInput(attrs={'type': 'date',
                                                                            'class': 'form-control'}))
    text = django_filters.CharFilter(label=_('Message contains'),
                                     field_name='text',
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = OutgoingSMS
        fields = ('message_type', 'sent_by', 'time_sent_min', 'time_sent_max', 'text')

    @property
    def qs(self):
        # We populate the queryset in the OutgoingSMSListView.get_queryset() method.
        # Without defining this method, the default FilterSet logic uses the constructed
        # queries from the declared fields above, which overwrites our queryset. We
        # cannot just depend on that because we need to filter only messages sent to this customer.
        # TODO: One possibility would be to add a hidden field that the template populates for the customer ID.
        return self.queryset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.form.fields:
            self.form.fields[field].widget.attrs.update({'class': 'form-control'})  # Add the bootstrap form-control attribute to all fields
            if isinstance(self.form.fields[field], django_filters.DateFilter):
                self.form.fields[field].widget.attrs.update({'type': 'date'})


class OutgoingSMSListView(SingleTableMixin, FilterView):

    model = OutgoingSMS
    table_class = OutgoingSMSTable
    view_title = "Outgoing"
    url_name = "customers:customer_outgoing_sms_history"
    filterset_class = OutgoingSMSFilter
    template_name = 'customers/outgoingsms_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Providing a value for 'add_url' enables the "Send new" button on the page
        if self.customer:
            context['add_url'] = reverse('customers:customer_send_outgoing_sms',
                                         kwargs={'pk': self.customer.pk})
            # Adding a customer is required to populate the breadcrumbs
            context['customer'] = self.customer
            context['title'] = self.view_title
            context['url_name'] = self.url_name
            context['breadcrumb_text'] = self.breadcrumb_text
        return context

    def get_queryset(self, **kwargs):
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        message_ids = SMSRecipient.objects.filter(recipient=self.customer,
                                                  page_index=1).values_list('message_id', flat=True)
        queryset = (OutgoingSMS.objects
                    .filter(id__in=message_ids)
                    .order_by('-time_sent', '-created')
                    .annotate(
                        sent_at=Subquery(SMSRecipient.objects.filter(message=OuterRef('pk'), recipient=self.customer)
                               .order_by('created')
                               .values('created')[:1])))

        method = self.request.method
        if method == "GET":
            params = self.request.GET
        elif method == "POST":
            params = self.request.POST

        if len(params) > 0:
            message_type = params.get('message_type')
            if message_type:
                queryset = queryset.filter(message_type=message_type)

            time_sent_min = params.get('time_sent_min')
            if time_sent_min:
                default_date = datetime.combine(datetime.now(),
                                                time(0, tzinfo=tz.gettz(settings.TIME_ZONE)))
                try:
                    date = parser.parse(time_sent_min, default=default_date)
                except parser.ParserError as e:
                    date = default_date
                queryset = queryset.filter(time_sent__gte=date)

            time_sent_max = params.get('time_sent_max')
            if time_sent_max:
                default_date = datetime.combine(datetime.now(),
                                                time(0, tzinfo=tz.gettz(settings.TIME_ZONE)))
                date = parser.parse(time_sent_max, default=default_date)
                queryset = queryset.filter(time_sent__lte=date)

            text = params.get('text')
            if text:
                queryset = queryset.filter(text__icontains=text)

            sent_by = params.get('sent_by')
            if sent_by:
                queryset = queryset.filter(sent_by=sent_by)

        return queryset

    @property
    def breadcrumb_text(self):
        return mark_safe("{} SMS History".format(self.view_title))


class SingleOutgoingSMSCreateView(SuccessMessageMixin, CreateView):

    model = OutgoingSMS
    template_name = 'customers/outgoingsms_form.html'
    form_class = SingleOutgoingSMSForm
    success_message = "Message sent"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.customer = Customer.objects.get(pk=self.kwargs['pk'])
        current_call_center = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            self.call_center = current_call_center.call_center
        else:
            self.call_center = None
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        out = self.object = form.save()
        out.message_type = OUTGOING_SMS_TYPE.INDIVIDUAL
        out.save(update_fields=["message_type"])
        try:
            sender = form.cleaned_data.get("senders")  # There should be only one sender_key...
            kwargs = {}
            task = getattr(self, 'task', None)
            if task and task.incoming_messages.exists():
                # Send the response to the phone number that triggered this
                in_msg = task.incoming_messages.last()
                if in_msg and in_msg.sender:
                    kwargs.update({'using_numbers': [in_msg.sender]})
            send_message.delay(
                self.object.id,
                [self.customer.id],
                sender=sender,
                exclude_stopped_customers=False,
                **kwargs
            )
        except Exception as e:
            if not self.object.get_extant_recipients():
                # we don't really want non-sent single-recipient SMSs lying around
                self.object.delete()
            form.add_error(None, e.args)
            return self.form_invalid(form)

        return response

    def get_success_url(self):
        return reverse('customers:customer_outgoing_sms_history',
                       kwargs={'pk': self.customer.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = self.customer
        return context

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        text, sender = sms_utils.get_populated_sms_templates_text(settings.SMS_SIGNATURE, self.customer)
        countries = [self.customer.border0.name] if self.customer and self.customer.border0 else []
        initial.update({
            'text': text,
            'sender': sender,
            'countries': countries,
        })
        return initial

    def get_form_kwargs(self) -> dict[str, Any]:
        form_kwargs = super().get_form_kwargs()
        if self.call_center:
            form_kwargs['call_center'] = self.call_center
        return form_kwargs


class CustomerActivityStreamView(ListView):

    model = Action
    paginate_by = 25
    context_object_name = 'actions'
    template_name = 'customers/activities.html'

    def get_queryset(self):
        self.customer = get_object_or_404(Customer, pk=self.kwargs['pk'])
        return self.customer.actor_actions.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['customer'] = self.customer
        page = self.request.GET.get('page', 1)
        if 'paginator' in ctx and ctx['paginator'] is not None:
            paginator = ctx['paginator']
            ctx['record_count'] = paginator.count
            if 'page_obj' in ctx and ctx['page_obj'] is not None:
                page_obj = ctx['page_obj']
                page_obj.page_range = paginator.get_elided_page_range(number=page)
        else:
            ctx['record_count'] = self.get_queryset().count()
        return ctx


class CustomerTipSentListView(SingleTableView):

    table_class = TipSentTable
    model = TipSent
    template_name = 'customers/tip_sent_list.html'

    def get_queryset(self, **kwargs):
        qs = super().get_queryset(**kwargs)
        return qs.filter(subscription__customer_id=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['customer'] = Customer.objects.get(pk=self.kwargs['pk'])
        return ctx
