import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from django.contrib import messages
from django.http import (HttpRequest, HttpResponse, HttpResponseRedirect,
                         JsonResponse)
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import UpdateView, View
from django.views.generic.detail import SingleObjectMixin

from django_tables2 import SingleTableView

from agri.constants import SUBSCRIPTION_FLAG
from callcenters.models import CallCenterOperator
from core.utils.functional import is_jquery_ajax
from customers.models import Customer, CustomerCommodity
from customers.views.customer import SingleOutgoingSMSCreateView
from sms.constants import OUTGOING_SMS_TYPE
from tasks.forms import (TaskBulkUpdateForm, TaskListFilterForm,
                         TaskSMSReplyForm, TaskUpdateForm)
from tasks.models import Task, TaskUpdate
from tasks.tables import TaskTable
from tasks.tasks import send_tasks_email_via_celery
from world.models import BorderLevelName
from world.utils import process_border_ajax_menus
from django.db.models import Q


class TaskTableView(SingleTableView):
    template_name = 'tasks/tasks.html'
    model = Task
    table_class = TaskTable
    form_class = TaskListFilterForm
    # pagination_class = LazyPaginator  # Performance improvement, preventing a count of all Tasks
    paginate_by = 25
    export_name = 'Exported Tasks'
    export_formats = ['csv', 'xlsx']
    exclude_columns = ["bulk", "edit"]

    def get_queryset(self):
        """
        Filters the QuerySet based on data entered via TaskListFilterForm.
        """
        self.form = self.form_class(self.request.GET)
        queryset = super().get_queryset().prefetch_related('assignees', 'customer').filter(customer__phones__isnull=False)
        user = self.request.user
        current_call_center = CallCenterOperator.objects.filter(operator=user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            border_query = f'customer__border{current_call_center.border_level}'
            queryset = queryset.filter(**{border_query: current_call_center.border_id})
        else:
            return queryset.none()

        if self.form.is_valid():
            # First extract the Status choice, since we have extra
            # choices beyond what is declared in the model. If no
            # status is selected by the user, we default to show
            # all open Tasks.
            status = self.form.cleaned_data.pop('status', "open")

            # Apply the status filter to the queryset separately because
            # we have additional options that are not valid status values in the DB.
            if status in Task.STATUS:
                queryset = queryset.filter(status=status)
            elif status == "open":
                queryset = queryset.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
            elif status == "closed":
                queryset = queryset.filter(status__in=(Task.STATUS.closed_resolved, Task.STATUS.closed_unresolved))
            elif status == "all":
                # No modification of the queryset
                pass
            else:
                # default to display all open Tasks
                queryset = queryset.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))

        # Apply location completeness filtering
        complete_location_value = self.form.cleaned_data.pop('complete_location')

        if complete_location_value == "Yes":
            condition = (
                Q(customer__border0__isnull=False) &
                Q(customer__border1__isnull=False) &
                Q(customer__border2__isnull=False) &
                Q(customer__border3__isnull=False)
            )
            queryset = queryset.filter(condition)

        elif complete_location_value == "No":
            condition = (
                Q(customer__border0__isnull=True) |
                Q(customer__border1__isnull=True) |
                Q(customer__border2__isnull=True) |
                Q(customer__border3__isnull=True)
            )
            queryset = queryset.filter(condition)

        # Build a dictionary mapping django field lookups => values
        # (e.g. {'customer__name__icontains': 'John Smith'}) with which to
        # filter the table's QuerySet.
        query_dict = dict([(self.form.query_string_mapping[k], v)
                            for k, v in
                            self.form.cleaned_data.items()
                            if v])

        queryset = queryset.filter(**query_dict)

        # Previously, by default, we sorted Tasks via priority, followed by date (oldest first)
        # queryset = queryset.annotate(
        #     priority_int=Case(
        #         When(priority="low", then=0),
        #         When(priority="medium", then=1),
        #         When(priority="high", then=2),
        #         When(priority="critical", then=3),
        #         output_field=IntegerField(),
        #         default=Value(1)  # unspecified Tasks default to medium priority
        #     )).order_by('-priority_int', 'created')

        #...however now the CCA's prefer sorting only via date (oldest first)
        queryset = queryset.order_by('created')

        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtered'] = self.form.data or False
        ctx['current_page_data'] = ctx['table'].page.object_list.data

        if 'bulk_update_form' not in ctx:
            ctx['bulk_update_form'] = TaskBulkUpdateForm(ctx['current_page_data'])

        selected_tasks = self.request.session.get('selected_tasks', [])
        ctx['selected_tasks'] = selected_tasks
        ctx['selected_tasks_count'] = len(selected_tasks)

        page = self.request.GET.get('page', 1)
        if 'paginator' in ctx and ctx['paginator'] is not None:
            paginator = ctx['paginator']
            ctx['record_count'] = paginator.count
            if 'table' in ctx and ctx['table'] is not None:
                table = ctx['table']
                table.page_range = paginator.get_elided_page_range(number=page)
        else:
            ctx['record_count'] = self.get_queryset().count()

        export_fields = []
        for key in self.table_class.base_columns.keys():
            if key in self.table_class.Meta.fields and key not in self.exclude_columns:
                title = self.table_class.base_columns[key].header
                if not title:
                    title = key.title()
                export_fields.append({'key': key, 'title': title})

        # Add GPS field manually
        #export_fields.append({'key': 'gps', 'title': 'GPS Coordinates'})

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
                                                 selected_border2s, selected_border3s, self.request.GET.dict())
            return JsonResponse(response)

        if 'HTTP_REFERER' in request.META:
            r = urlparse(request.META['HTTP_REFERER'])
            # If this is not a request for another paginated page then clear the session selected Tasks data.
            if r.netloc != request.get_host() or r.path != request.path:
                if 'selected_tasks' in request.session:
                    del request.session['selected_tasks']
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # If a jquery ajax request
        if is_jquery_ajax(self.request):
            if 'export-tasks' in request.POST:
                fields = dict(request.POST)
                fields.pop('csrfmiddlewaretoken', None)
                fields.pop('export-tasks', None)
                export_format = fields.pop('export-format', 'csv')
                if isinstance(export_format, list):
                    export_format = export_format[0]
                selected_tasks = request.session.get('selected_tasks', [])
                # Spawn a celery task to generate and email this export
                send_tasks_email_via_celery.delay(request.user.email, selected_tasks, list(fields.keys()), export_format)
                response = JsonResponse({'success': True, 'user_email': request.user.email})
                return response
            else:
                # Update user session with the selected tasks so that the selection persists across pages
                tasks = json.loads(request.body)
                if tasks is None:
                    selected_tasks = []
                elif tasks == 'all':
                    # Get list of all filtered tasks (as strings)
                    selected_tasks = list(map(str, self.get_queryset().values_list('id', flat=True)))
                else:
                    selected_tasks = request.session.get('selected_tasks', [])
                    for t in tasks:
                        if t and tasks[t] and t not in selected_tasks:
                            selected_tasks.append(t)
                        elif t and not tasks[t] and t in selected_tasks:
                            selected_tasks.remove(t)

                self.request.session['selected_tasks'] = selected_tasks
                response_data = {
                    'tasks_selected_count': len(selected_tasks)
                }
                response = JsonResponse(response_data)
                return response

        # Not an ajax post
        self.object_list = self.get_queryset()
        ctx = self.get_context_data(**kwargs)
        # Get the Task IDs from the session, otherwise the form submission
        task_ids = request.session.get('selected_tasks', request.POST.getlist('bulk-tasks'))

        if 'bulk-sms' in request.POST:
            # The user submitted the bulk sms form.
            customer_ids = set(Task.objects.filter(pk__in=task_ids).values_list('customer_id', flat=True))
            bulk_close_tasks = request.POST.get('bulk_close_tasks') == 'on'

            # apply network filters so that the customer count in the sms compose will be correct
            customers = Customer.objects.filter(pk__in=customer_ids, has_requested_stop=False)

            # Convert the filtered list back into a list of pk's
            customer_ids = list(customers.values_list('pk', flat=True))

            # Pack the session data, similar to how CustomerFilterFormView would
            self.request.session['bulk_customer'] = {
                'task_ids': task_ids,
                'form_data': customer_ids,
                'count': len(customer_ids),
                'bulk_close_tasks': bulk_close_tasks,
                # Override the default customer view success url, to return to the tasks view
                'success_url': 'task_list'
            }

            # The user took action on their selections so clear them from the session
            if 'selected_tasks' in request.session:
                del request.session['selected_tasks']

            next_url = reverse_lazy('core_management_customer_bulk_compose')
            return HttpResponseRedirect(next_url)
        elif 'update' in request.POST:
            # Else the user submitted the bulk-update form
            tasks = Task.objects.filter(pk__in=task_ids)
            data = dict(self.request.POST)
            # All items are now lists, which we don't want. Only MultipleChoiceField
            # and ModelMultipleChoiceField need to be lists, so convert priority and statys to simple data types.
            # We assume that a value of length 1 is a list, so we grab the first element.
            for key in ('bulk-priority', 'bulk-status', 'bulk-tips_commodity'):
                if key in data and isinstance(data[key], (list, tuple)):
                    data[key] = data[key][0]

            data.update({'bulk-tasks': task_ids})
            form = TaskBulkUpdateForm(tasks, data=data)

            if form.is_valid():
                return self.form_valid(form)
            else:
                return self.form_invalid(form)
        # else:
            # We want exports to come as POST requests to keep the URL params clean. However,
            # exports expects them to come via GET, so we need to move some params to make that work.
            # if self.export_trigger_param not in request.GET:
            #     request.GET._mutable = True
            #     export_format = request.POST.get('export-action', 'export-csv').split('-')[-1]
            #     request.GET.update({self.export_trigger_param: export_format})
            #     request.GET._mutable = False

            # Set the object_list to be only the selected tasks
            # self.object_list = Task.objects.filter(pk__in=task_ids)

            # The export action does not redirect nor refresh the current page,
            # so don't reset the selected_tasks session data as this will confuse the user.
            # if 'selected_tasks' in self.request.session:
            #     del self.request.session['selected_tasks']

            # Now generate the export
            # return super().render_to_response(ctx, **kwargs)

    # If the bulk update form is valid...
    def form_valid(self, form):
        for task in form.cleaned_data['tasks']:
            for field in set(form.changed_data).intersection(['status', 'priority']):
                # If the status changed, create a TaskUpdate to reflect the change
                if field == 'status' and task.status != form.cleaned_data[field]:
                    TaskUpdate.objects.create(
                        task=task,
                        status=form.cleaned_data[field],
                        creator_id=self.request.user.id,
                        last_editor_id=self.request.user.id,
                    )
                # Then set the new attribute on the Task. This update needs to come after the
                # TaskUpdate object creation because we check the original field value above.
                setattr(task, field, form.cleaned_data[field])

            task.save(user=self.request.user)

            categories_remove = form.cleaned_data.get('categories_remove')
            categories_add = form.cleaned_data.get('categories_add')
            if categories_remove:
                task.customer.categories.remove(*categories_remove)
            if categories_add:
                task.customer.categories.add(*categories_add)

            # Broken into separate loops as we need to set last_editor_id on the task prior to
            # updating the m2m fields to ensure the correct activity stream event is generated.
            for field in set(form.changed_data).intersection(['tags_remove', 'assignees_remove']):
                m2m_field = field.replace('_remove', '')
                manager = getattr(task, m2m_field)
                manager.remove(*form.cleaned_data[field])
            # NOTE: Adding the new data to the manager also saves it to the m2m field in the db.
            for field in set(form.changed_data).intersection(['tags_add', 'assignees_add']):
                m2m_field = field.replace('_add', '')
                manager = getattr(task, m2m_field)
                manager.add(*form.cleaned_data[field])

            # commodities
            customer = task.customer
            commodities_remove = form.cleaned_data.get('commodities_remove')
            commodities_add = form.cleaned_data.get('commodities_add')
            if commodities_remove:
                customer.commodities.remove(*commodities_remove)
            if commodities_add:
                customer.commodities.add(*commodities_add)
            tips_commodity = form.cleaned_data.get('tips_commodity')

            if tips_commodity:
                CustomerCommodity.objects.update_or_create(
                    customer=customer,
                    commodity=tips_commodity,
                    defaults={'subscription_flag': SUBSCRIPTION_FLAG.FREEMIUM}
                )
                CustomerCommodity.objects.filter(
                    customer=customer, subscription_flag=SUBSCRIPTION_FLAG.FREEMIUM
                ).exclude(commodity=tips_commodity).update(subscription_flag=None)
                Customer.index_one(customer)

        # The user took action on their selections so clear them from the session
        if 'selected_tasks' in self.request.session:
            del self.request.session['selected_tasks']

        return self.render_to_response(self.get_context_data())

    def form_invalid(self, form):
        """ Handles incorrect input to the `TaskBulkUpdateForm`.
        """
        # Add form.errors to the view's messages so they are obvious to see
        for error in form.errors.keys():
            for message in form.errors[error]:
                messages.error(self.request, message)
        return self.render_to_response(
            self.get_context_data(bulk_update_form=form))


class TaskUpdateView(UpdateView):
    template_name = 'tasks/task_update.html'
    model = Task
    form_class = TaskUpdateForm
    context_object_name = 'task'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        current_call_center = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            self.call_center = current_call_center.call_center
        else:
            self.call_center = None
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('task_update', kwargs={'pk': self.get_object().id})

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        initial = super().get_initial()
        task = self.get_object()
        customer = task.customer
        initial.update({
            'customer': customer.id,  # This MUST be named customer and must contain an integer ID, otherwise form.changed_data believes the customer changed
            'task': task,
            'priority': task.priority,
            'status': task.status,
            'assignees': list(task.assignees.values_list('id', flat=True)),
            'tags': list(task.tags.values_list('id', flat=True)),
        })
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        customer = task.customer
        initial = kwargs.get('initial', self.get_initial())

        if customer and customer.border0:
            initial.update({
                'countries': [customer.border0.name]
            })
            context['borderlevel1_name'] = BorderLevelName.objects.get(country=customer.border0.name, level=1).name
            context['borderlevel2_name'] = BorderLevelName.objects.get(country=customer.border0.name, level=2).name
            context['borderlevel3_name'] = BorderLevelName.objects.get(country=customer.border0.name, level=3).name

        kwargs.update({
            'initial': initial,
        })

        if 'form' in kwargs and kwargs.get('form') is not None:
            # This view has two forms. Instantiating the TaskSMSReplyForm and passing
            # in the TaskUpdateForm as 'form' in kwargs causes problems, so remove it
            # from the kwargs here and add it to the context.
            task_update_form = kwargs.pop('form')
            context.update({'form': task_update_form})    # Used directly in the html template
        kwargs['call_center'] = self.call_center
        context['sms_form'] = TaskSMSReplyForm(**kwargs)  # Used directly in the html template
        return context

    def form_valid(self, form):
        """
        Overridden to populate the `last_editor_id` property to the
        current logged-in User and create a corresponding TaskUpdate object.
        """
        # If the form didn't change, don't modify the DB objects.
        if hasattr(form, 'changed_data') and form.changed_data:
            self.object = form.save(commit=False)
            self.object.save(user=self.request.user)
            form.save_m2m()
            # Right now TaskUpdate only tracks status changes
            if 'status' in form.changed_data:
                TaskUpdate.objects.create(
                    task=self.object,
                    status=self.object.status,
                    creator_id=self.request.user.id,
                    last_editor_id=self.request.user.id,
                )

        return HttpResponseRedirect(self.get_success_url())


class CannotContactCustomerView(SingleObjectMixin, View):
    """
    Track number of contact attempts and send SMS when limit is reached.
    """
    http_method_names = ['post', 'options', ]
    model = Task

    def get_success_url(self):
        return reverse('task_update', args=(self.task.id,))

    def post(self, request, *args, **kwargs):
        self.task = self.get_object()
        self.task.add_cannot_contact_customer_update(user=self.request.user)
        self.task.save(user=self.request.user)
        # We do not create a TaskUpdate object here because a status change
        # has not occurred even though the last editor of the task may have.
        return HttpResponseRedirect(self.get_success_url())


class TaskSMSReplyView(SingleOutgoingSMSCreateView):

    form_class = TaskSMSReplyForm

    def dispatch(self, request, *args, **kwargs):
        self.task = get_object_or_404(Task, pk=self.kwargs['task_pk'])
        current_call_center = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id').first()
        if current_call_center:
            self.call_center = current_call_center.call_center
        else:
            self.call_center = None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        form_args = super().get_form_kwargs(**kwargs)

        form_data = form_args.get('data', {}).copy()
        form_data['task'] = self.task.id
        form_data['sent_by_id'] = self.request.user.id
        form_args['call_center'] = self.call_center

        form_args['data'] = form_data
        return form_args

    def get_success_url(self):
        # Redirect to the task update page so the user can see that the response was sent
        url = super().get_success_url()
        if hasattr(self, 'task'):
            # If the form was posted successfully, return to the task update view so the user can see.
            url = reverse('task_update', kwargs={'pk': self.task.pk})

        return url

    def post(self, request, *args, **kwargs):
        # There's a risk of duplicate js submissions when the CCA has poor internet
        # connectivity. We try to identify and suppress duplicates here.
        # For our heuristic, we assume any messages sent by the same user to the same customer
        # from the same task with the same message text within the last 10 minutes is a duplicate.
        debounce_time = timezone.now() - timedelta(minutes=10)
        txt = request.POST.get('text')
        duplicates = self.task.outgoing_messages.filter(sent_by=request.user,
                                                        time_sent__gte=debounce_time,
                                                        text=txt).count()
        # If this appears to be a duplicate, return a json success, so the client stops submitting
        if duplicates:
            return JsonResponse({'success': True})
        else:
            # If not a duplicate, handle normally
            response = super().post(request, *args, **kwargs)
            return response

    def form_valid(self, form):
        response = super().form_valid(form)
        # The generic super class categorizes messages as individual,
        # but here we are sending a task. Not the most efficient
        # solution here but new task messages are not high volume.
        out = self.object
        out.message_type = OUTGOING_SMS_TYPE.TASK_RESPONSE
        out.extra.update({'task_id': self.task.id})
        # In many cases, the sms message will not have been saved
        # to the DB yet at this point. If it has, then update it.
        if out.pk is not None:
            out.save(update_fields=["message_type", "extra"])

        return response
