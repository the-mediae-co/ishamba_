from datetime import timedelta
import json
from logging import getLogger
from typing import Any, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import MultipleChoiceField
from django.forms.models import ModelMultipleChoiceField
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse, HttpResponse
from django.template.defaultfilters import pluralize
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import View, FormView
from callcenters.models import CallCenter, CallCenterOperator

from core.logger import log
from core.utils.functional import is_jquery_ajax
from customers.models import Customer, CustomerQuestion, CustomerQuestionAnswer
from sms.tasks import send_message
from tasks.models import Task, TaskUpdate
from ishamba.settings import ELECTRICITY_QUESTION, IRRIGATION_WATER_QUESTION
from world.utils import process_border_ajax_menus
from agri.constants import SUBSCRIPTION_FLAG
from sms.forms import BulkOutgoingSMSForm, CustomerFilterForm, BaseIncomingSMSForm
from sms.models import OutgoingSMS
from sms.utils import get_l10n_response_template_by_name, populate_templated_text, get_i10n_template_text
from sms.constants import KENYA_COUNTRY_CODE, OUTGOING_SMS_TYPE, UGANDA_COUNTRY_CODE, ZAMBIA_COUNTRY_CODE
from sms.signals.handlers import sms_received
from world.models import Border

from gateways.views import IPAuthorizationMixin

import sentry_sdk

logger = getLogger(__name__)


class BaseFilterFormView(LoginRequiredMixin, FormView):
    """
    This is the base view used for both CustomerFilterFormView below, and
    payments.views.OfferFilterCustomersView.

    Views subclassing this will need to define a `form_valid_next(customers)`
    method.
    """
    form_class = CustomerFilterForm
    call_center: Optional[CallCenter]

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        current_call_center = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            self.call_center = current_call_center.call_center
        else:
            self.call_center = None
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        object_list = self.model.objects.filter(
            phones__isnull=False
        )
        if self.call_center:
            border_query = f'border{self.call_center.border.level}'
            object_list = object_list.filter(**{border_query: self.call_center.border.id})

        search_term = self.request.GET.get('search', '')
        if search_term:
            object_list = object_list.search(search_term,
                                             headline_field='snippet',
                                             headline_document='_body_rendered')
        tag = self.request.GET.get('tag', '')
        if tag:
            object_list = object_list.filter(tags__name=tag)
        return object_list

    def get_form_kwargs(self):
        """
        Amends base method to perform the kwargs.update step also when form is
        submitted by GET.
        We also insert some view-specific form attributes if they're specified
        on this class.
        """
        kwargs = {'initial': self.get_initial(), 'prefix': self.get_prefix()}

        if self.request.method in ('POST', 'PUT'):
            kwargs.update({'data': self.request.POST})
        elif self.request.method in ('GET') and is_jquery_ajax(self.request):  # ajax
            kwargs.update({'data': self.request.GET})

        if getattr(self, 'form_action', None):
            if getattr(self, 'offer', None):
                kwargs['action'] = reverse(self.form_action, args=[self.offer.id])
            else:
                kwargs['action'] = self.form_action

        if getattr(self, 'form_button_text', None):
            kwargs['button_text'] = self.form_button_text

        if self.call_center:
            kwargs['call_center'] = self.call_center

        return kwargs

    def get(self, request, *args, **kwargs):
        """
        Mimic self.post
        """
        form_class = self.get_form_class()
        form = self.get_form(form_class)

        if form.is_bound:
            if form.is_valid():
                return self.form_valid(form)
            else:
                return self.form_invalid(form)

        # Page is just a plain GET with no submit.
        context = self.get_context_data(form=form)

        return self.render_to_response(context)

    def form_valid(self, form):
        """
        Don't redirect if not submitted via POST.
        """
        # If a jquery ajax request
        if is_jquery_ajax(self.request):
            if hasattr(form, 'cleaned_data'):  # if form is valid, this should always be true
                selected_border0s = form.cleaned_data.get('border0', [])
                selected_border1s = form.cleaned_data.get('border1', [])
                selected_border2s = form.cleaned_data.get('border2', [])
                selected_border3s = form.cleaned_data.get('border3', [])
                if self.request.method == 'POST':
                    request_data = self.request.POST.dict()
                else:
                    request_data = self.request.GET.dict()
                response = process_border_ajax_menus(selected_border0s, selected_border1s,
                                                     selected_border2s, selected_border3s,
                                                     request_data)
                # Populate the fields necessary to draw this location on the leaflet map
                if response['selected_border3s']:
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

            # With the ripple effect of the border selections sorted, correct
            # the form and get the corresponding customer count
            if 'border0' in form.cleaned_data:
                form.cleaned_data['border0'] = Border.objects.filter(pk__in=response['selected_border0s'])
            if 'border1' in form.cleaned_data:
                form.cleaned_data['border1'] = Border.objects.filter(pk__in=response['selected_border1s'])
            if 'border2' in form.cleaned_data:
                form.cleaned_data['border2'] = Border.objects.filter(pk__in=response['selected_border2s'])
            if 'border3' in form.cleaned_data:
                form.cleaned_data['border3'] = Border.objects.filter(pk__in=response['selected_border3s'])

            ctx = self.get_context_data(form=form)

            response.update({
                'rendered_customer_count': render_to_string('sms/includes/customer_count.html', ctx),
            })
            return JsonResponse(response)

        ctx = self.get_context_data(form=form)

        if self.request.method in ('POST', 'PUT'):
            if ctx['count']:
                return self.form_valid_next(form, ctx['customers'], ctx['count'])
            form.add_error(None, _("You must select some customers"))
            return self.form_invalid(form)

        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        form = kwargs.get('form')
        customers = Customer.objects.filter(phones__isnull=False)
        if self.call_center:
            border_query = f'border{self.call_center.border.level}'
            customers = customers.filter(**{border_query: self.call_center.border.id})

        filtered = self.filter_customers(customers, form)

        if form and form.is_valid():
            # A valid form returns cleaned data
            count = filtered.count()
        else:
            # A non-valid form returns zero customers, but we
            # want to display the full customer count instead
            count = form.count

        ctx.update({
            'customers': filtered,
            'count': count
        })
        return ctx

    @staticmethod
    def filter_customers(customers, form):
        if not (form and form.is_valid()):
            # Bail if we don't have a valid form
            return Customer.objects.none()

        query_dict = dict(
            (form.query_string_mapping[k], v)
            for k, v in form.cleaned_data.items()
            if bool(v) or v is False  # False but not '', [], None etc.
        )

        logger.debug(f"filter_customers-query_dict: {query_dict}")

        try:
            electricity_key = CustomerQuestion.objects.filter(text=ELECTRICITY_QUESTION).first().id
        except AttributeError:
            electricity_key = None

        try:
            irrigation_water_key = CustomerQuestion.objects.filter(text=IRRIGATION_WATER_QUESTION).first().id
        except AttributeError:
            irrigation_water_key = None

        # handle fields related to radius based filter
        distance_range = query_dict.pop('distance_range', '')
        # location = query_dict.pop('location', '')
        lat = query_dict.pop('lat', '')
        lng = query_dict.pop('lng', '')
        if lat and lng and distance_range:
            location = Point(x=lng, y=lat, srid=4326)
            customers = customers.filter(
                location__distance_lte=(location, D(km=distance_range))
            )

        can_access_call_centre = query_dict.pop('can_access_call_centre', '')
        has_electricity = query_dict.pop('has_electricity', '')
        has_irrigation_water = query_dict.pop('has_irrigation_water', '')
        premium_subscriber = query_dict.pop('premium_subscriber', '')
        gender = query_dict.pop('gender', '')
        location__isnull = query_dict.pop('location__isnull', False)
        tip_subscriptions = query_dict.pop('tip_subscriptions', [])

        if premium_subscriber == "Yes":
            customers = customers.premium()
        elif premium_subscriber == "No":
            customers = customers.non_premium()

        if gender == 'u':
            customers = customers.filter(sex='')
        elif gender:
            customers = customers.filter(sex__istartswith=gender)

        if location__isnull:
            customers = customers.filter(location__isnull=True)

        # handle phone filter
        phones = query_dict.pop('phone__in', None)
        if phones:
            customers = customers.filter(phones__number__in=phones)

        if can_access_call_centre:
            customers = customers.can_access_call_centre()

        # Ensure stopped customers are excluded regardless of filter settings
        customers = customers.exclude(has_requested_stop=True)

        task_tags = query_dict.pop('task_tags', '')
        if task_tags:
            customer_ids = Task.objects.filter(tags__pk__in=task_tags).values_list("customer_id", flat=True)
            customers = customers.filter(pk__in=customer_ids)

        # Exclude customers with country codes outside our operating areas.
        customers = customers.filter(
            Q(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}") |
            Q(phones__number__startswith=f"+{UGANDA_COUNTRY_CODE}") |
            Q(phones__number__startswith=f"+{ZAMBIA_COUNTRY_CODE}")
        )

        if electricity_key and has_electricity != "ALL":
            electricity_customer_ids = CustomerQuestionAnswer.objects.filter(
                question_id=electricity_key, text__icontains=has_electricity
            ).values_list('customer_id', flat=True)
            customers = customers.filter(pk__in=electricity_customer_ids)

        if irrigation_water_key and has_irrigation_water != "ALL":
            irrigation_water_customer_ids = CustomerQuestionAnswer.objects.filter(
                question_id=irrigation_water_key, text__icontains=has_irrigation_water
            ).values_list('customer_id', flat=True)
            customers = customers.filter(pk__in=irrigation_water_customer_ids)

        if tip_subscriptions:
            customers = customers.filter(
                customer_commodities__commodity__in=tip_subscriptions,
                customer_commodities__subscription_flag__in=[SUBSCRIPTION_FLAG.FREEMIUM, SUBSCRIPTION_FLAG.PREMIUM]
            )

        # finally, filter the customers using any remaining filters
        # logger.debug(f"filter_customers-query_dict: {query_dict}")
        customers = customers.filter(**query_dict).order_by('id').distinct('id')
        # customers = customers.filter(**query_dict)
        # logger.debug(f"filter_customers-final: {customers.query}")
        # logger.debug(f"filter_customers-final: {customers.count()} customers")
        # logger.debug(f"filter_customers-final: {customers.explain()} customers")
        return customers


class CustomerFilterFormView(BaseFilterFormView):
    template_name = 'sms/bulk_sms_filter_form.html'
    success_url = reverse_lazy('core_management_customer_bulk_compose')
    form_action = 'core_management_customer_filter'
    form_button_text = 'Compose SMS'

    def form_valid_next(self, form, customers, count):
        # The issue here is that we have a nicely validated form and nicely constructed
        # queryset that we have no use for. This form is merely a step towards
        # next form in which we will collect more data (e.g. actual message text to
        # send in the bulk SMS), and that's when we will really need the queryset.
        # Previous solution was to convert customers queryset into a list of PKs,
        # save that whole list into the session, and rebuild the queryset from PKs in the
        # next form submission. We avoid such monstrosity by being hackish - we save
        # form data so we can rebuild a previously submitted form, and then rebuild
        # query set from the form data.

        # form.data is a QueryDict, including all of its problems. For passing the
        # form data through the session, convert it to a better representation (dict).
        session_form_dict = dict(form.data)
        # All items are now lists, which we don't want. Only MultipleChoiceField
        # and ModelMultipleChoiceField need to be lists, so convert all others to simple data types.
        # We assume that a value of length 1 is a list, so we grab the first element.
        cleaned_dict = {k: v if len(v) > 1 or len(v) == 0 or
                                isinstance(form.fields.get(k), ModelMultipleChoiceField) or
                                isinstance(form.fields.get(k), MultipleChoiceField)
                             else v[0] for k, v in session_form_dict.items()}

        self.request.session['bulk_customer'] = {
            'form_data': cleaned_dict,
            'count': count,
        }
        return HttpResponseRedirect(self.success_url)


class BulkOutgoingSMSCreateView(SuccessMessageMixin, FormView):
    """
    There's no url for this, only accessed as 'step 2' of the filter view
    above or via the Task->Send Bulk SMS view.
    """
    model = OutgoingSMS
    template_name = 'sms/bulk_sms_compose_form.html'
    form_class = BulkOutgoingSMSForm
    success_message = "Bulk message sent"
    success_url = 'core_management_customer_filter'
    call_center: Optional[CallCenter]

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        current_call_center = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            self.call_center = current_call_center.call_center
        else:
            self.call_center = None
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super().get_initial()
        if self.call_center:
            country = self.call_center.country
        else:
            countries = self.get_customer_countries()
            if not countries:
                # If we cannot determine the countries from the customer list, guess Kenya.
                # This is only used to pre-populate some default text, so assuming Kenya is ok.
                countries = Border.objects.filter(name='Kenya', level=0)
            country = countries.order_by('?').first()  # If there are multiple countries, pick one at random
        response_template = get_l10n_response_template_by_name(settings.SMS_SIGNATURE, country)
        if response_template is None:
            # If the response template was not found, guess Kenya and try again
            response_template = get_l10n_response_template_by_name(settings.SMS_SIGNATURE + '_Kenya', country)
            if response_template is None:
                sentry_sdk.capture_message(f"Could not find template {settings.SMS_SIGNATURE}. Country = {country}")

        if response_template is not None:

            # Get the preferred language response text for this message.
            session_data = self.get_data()
            form_data = session_data.get('form_data')
            # Management -> bulk_sms sends form_data as a dict. Task -> send sms sends form data as a list of customers
            if form_data and isinstance(form_data, dict):
                preferred_language = form_data.get('preferred_language')
                if preferred_language:
                    text = get_i10n_template_text(response_template, preferred_language[0])
                else:
                    text = populate_templated_text(response_template.translations.first().text)
            else:
                text = ''
        else:
            text = ''

        initial.update({'text': text})
        return initial

    def get_data(self):
        if not hasattr(self, '_data'):
            self._data = self.request.session.get('bulk_customer', {})
        return self._data

    def clear_data(self):
        if 'bulk_customer' in self.request.session:
            del self.request.session['bulk_customer']

    def get_customer_queryset(self):
        # We load from the session the form data for a previously submitted CustomerFilterForm,
        # rebuild the form, and then recreate the customer queryset from the form.
        if hasattr(self, '_customer_qs') and self._customer_qs is not None:
            return self._customer_qs

        form_data = self.get_data().get('form_data')
        if form_data is None:
            return Customer.objects.none()
        elif isinstance(form_data, list):
            self._customer_qs = Customer.objects.filter(pk__in=form_data, has_requested_stop=False)
            return self._customer_qs
        form = CustomerFilterForm(data=form_data)
        if self.call_center:
            border_query = f'border{self.call_center.border.level}'
            cc_customers = Customer.objects.filter(**{border_query: self.call_center.border.id})
        else:
            cc_customers = Customer.objects.all()
        self._customer_qs = BaseFilterFormView.filter_customers(
            customers=cc_customers,
            form=form
        )
        return self._customer_qs

    def get_customer_countries(self):
        """
        Returns a queryset of distinct countries that the recipients reside in
        """
        # While it would be more efficient to extract the border0 id's from
        # the form data, users can also specify individual phone numbers, as
        # well as filter all customers by other criterion.
        customers = self.get_customer_queryset()
        country_ids = customers.order_by('border0_id').distinct('border0_id').values_list('border0_id', flat=True)
        countries = Border.objects.filter(id__in=country_ids, level=0)
        return countries

    def get(self, request, *args, **kwargs):
        if not self.get_data().get('count'):
            messages.info(
                request,
                _('No customers selected, redirecting you back to the customer '
                  'selection form.'))
            return HttpResponseRedirect(self.get_success_url())

        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        """
        We're not subclassing the base method here, just mostly replicating
        it and adding object.send().
        Note that because of this we also have to repeat the work otherwise
        performed by SuccessMessageMixin. Therefore, SuccessMessageMixin can
        be removed from the inheritance above, but it is clearer to devs to
        leave it in place.
        """
        kwargs = {}
        data = self.get_data()

        # If sent from Task "send bulk sms response" form
        bulk_close_tasks = data.get('bulk_close_tasks')
        task_ids = data.get('task_ids')

        # Update the OutgoingSMS auto fields
        user_id = self.request.user.id
        form.instance.sent_by_id = user_id
        form.instance.creator_id = user_id
        form.instance.last_editor_id = user_id
        form.instance.time_sent = timezone.now()

        # If there are tasks associated with this sms, then the message type is TASK_RESPONSE
        if task_ids:
            form.instance.message_type = OUTGOING_SMS_TYPE.TASK_RESPONSE
            form.instance.extra = {'task_id': json.dumps(task_ids)}
        else:
            form.instance.message_type = OUTGOING_SMS_TYPE.BULK
            task_ids = []  # Prevent errors in the loop below

        # Save the OutgoingSMS instance
        outgoing_sms = self.object = form.save()

        success_url = data.get('success_url', None)
        # If not redirecting to the customer filter form...
        if success_url:
            self.success_url = success_url

        customers = self.get_customer_queryset()
        total_customers = customers.count()
        eta = form.cleaned_data.get('send_at')

        if settings.ENFORCE_BLACKOUT_HOURS:
            this_hour_local = timezone.localtime(timezone.now()).hour
            eta_hour = eta.hour if eta else this_hour_local

            if not eta and not (settings.BLACKOUT_END_HOUR <= this_hour_local <= settings.BLACKOUT_BEGIN_HOUR):
                # If no eta was provided and we're not within the allowed sending hours,
                # delay sending until the next acceptable hour
                eta = timezone.localtime(timezone.now())

            new_eta = eta

            if eta_hour < settings.BLACKOUT_END_HOUR:
                # Early morning
                new_eta = eta + timedelta(hours=settings.BLACKOUT_END_HOUR - eta_hour)
            elif eta_hour > settings.BLACKOUT_BEGIN_HOUR:
                # Late evening
                new_eta = eta + timedelta(hours=(24 - eta_hour + settings.BLACKOUT_END_HOUR))
            if new_eta != eta:
                logger.debug(f"BLACKOUT: message {outgoing_sms} scheduled "
                             f"{eta}, delaying until {new_eta}")
                sentry_sdk.capture_message(f"BLACKOUT: message {outgoing_sms} scheduled "
                                           f"{eta}, delaying until {new_eta}")
                eta = new_eta
        if eta:
            # Celery kwargs
            task_kwargs = {'eta': eta}
        else:
            task_kwargs = {}

        try:
            senders = form.cleaned_data['senders']
            if not senders:
                raise ValidationError(f"Configuration error: Sender not present in form data: "
                                      f"{form.cleaned_data.keys()}")

            logger.debug(
                f"BulkOutgoingSMSCreateView:form_valid: sending OutgoingSMS({outgoing_sms.id}) "
                f"to {customers.count()} customers from {senders}")
            kwargs['sender'] = senders
            send_message.apply_async([outgoing_sms.id, list(customers.values_list('id', flat=True))], kwargs, **task_kwargs)

            for task_id in task_ids:
                try:
                    task = Task.objects.get(id=task_id)
                    task.outgoing_messages.add(outgoing_sms)
                    if bulk_close_tasks:
                        # Create a TaskUpdate to reflect the change
                        TaskUpdate.objects.create(
                            task=task,
                            status=Task.STATUS.closed_resolved,
                            creator_id=self.request.user.id,
                            last_editor_id=self.request.user.id,
                        )
                        # Then set the new attribute on the Task. The update
                        # needs to come after the TaskUpdate object creation
                        setattr(task, 'status', Task.STATUS.closed_resolved)

                        task.last_editor_id = self.request.user.id
                        task.save()

                except Task.DoesNotExist as e:
                    sentry_sdk.capture_message(f"Task not found when sending OutgoingSMS: {task_id}, {e}")
        except ValidationError as e:
            if not outgoing_sms.get_extant_recipients():
                # we don't really want non-sent outgoing SMSs lying around
                outgoing_sms.delete()
            if e.message:
                form.add_error(None, e.message)
            else:
                log.exception(e)
                messages.warning(
                    self.request,
                    _("Attempting to send this SMS caused an error with no "
                      "info supplied. An error notification has been sent."))
            return self.form_invalid(form)

        self.clear_data()

        # success_message = self.get_success_message(form.cleaned_data)
        success_message = f"{self.success_message} to {customers.count()} customer{pluralize(customers.count())}"
        if bulk_close_tasks:
            success_message += f", {len(task_ids)} task{pluralize(len(task_ids))} Closed:Resolved"
        if success_message:
            messages.success(self.request, success_message)
            logger.debug(f"BulkOutgoingSMSCreateView: {total_customers} recipients, {success_message}")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['count'] = self.get_data().get('count')
        return ctx

    def get_form_kwargs(self) -> dict[str, Any]:
        form_kwargs = super().get_form_kwargs()
        if self.call_center:
            form_kwargs['call_center'] = self.call_center
        return form_kwargs


class BaseIncomingSMSView(IPAuthorizationMixin, View):
    """
    Base view for the handling of incoming SMS messages delivered via URL
    callback.
    """

    http_method_names = ['post']  # limit to POST requests
    gateway = None
    form = BaseIncomingSMSForm

    def post(self, request, *args, **kwargs):
        form = self.form(request.POST)

        if not form.is_valid():
            logger.warning('IncomingSMS form invalid: %s', form.errors,
                           extra={'post_data': request.POST})
            return HttpResponse('')

        incoming_sms = form.save(commit=False)
        incoming_sms.gateway = self.gateway.Meta.gateway_id

        # send a signal that so that the individual Django project can process
        # messages in the required manner.
        sms_received.send(sender=self.__class__, instance=incoming_sms)

        return HttpResponse('')
