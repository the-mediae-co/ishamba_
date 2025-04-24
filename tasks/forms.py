import sentry_sdk
from crispy_forms.bootstrap import FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Layout, Submit
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import BLANK_CHOICE_DASH, Value
from django.db.models.functions import Concat
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from django_select2 import forms as s2forms
from taggit.models import Tag

from agri.models import Commodity
from core.widgets import AuthModelSelect2MultipleWidget, AuthModelSelect2Widget
from customers.models import Customer
from sms.constants import OUTGOING_SMS_TYPE
from sms.forms import SingleOutgoingSMSForm
from world.models import Border, BorderLevelName
from world.utils import get_border0_choices

from tasks.models import Task, TaskUpdate
from customers.models import CustomerCategory


def _get_users_qs():
    return User.objects.order_by('-is_active', Lower('username'))


def _get_users():
    return _get_users_qs().values_list('pk', 'username')


def _get_active_users_qs():
    return _get_users_qs().filter(is_active=True)


def _get_active_users():
    return _get_active_users_qs().values_list('pk', 'username')


def _get_task_tags_qs():
    return Task.tags.order_by(Lower('name'))


def _get_task_tags():
    return _get_task_tags_qs().values_list('pk', 'name')


def _get_tags_qs():
    return Tag.objects.order_by(Lower('name'))


def _get_tags():
    return _get_tags_qs().values_list('pk', 'name')


def _get_border1s():
    border1_qs = Border.objects.filter(level=1) \
        .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
    border1_options = [(c[0], c[1]) for c in border1_qs
        .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
    return border1_options


class TaskUpdateCreateForm(forms.ModelForm):
    class Meta:
        model = TaskUpdate
        fields = ('message', 'status', )

    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop('task')
        instance = kwargs.get('instance', None)

        if instance is None:
            # if we didn't get an instance, instantiate a new one
            instance = TaskUpdate(task=self.task)
        kwargs['instance'] = instance

        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        previous_status = self.task.status
        new_status = data['status']
        if previous_status == new_status and not data.get('message'):
            raise ValidationError("Either enter a message, or change the "
                                  "status, otherwise this update is doing "
                                  "nothing.")
        return data


class TaskBulkUpdateForm(forms.Form):

    prefix = 'bulk'

    tasks = forms.ModelMultipleChoiceField(
        Task.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=False)
    assignees_add = forms.MultipleChoiceField(
        required=False,
        choices=_get_active_users,
        label=_("Add Assignees"),
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Add an Assignee',
            },
        )
    )
    assignees_remove = forms.MultipleChoiceField(
        required=False,
        choices=_get_users,
        label=_("Remove Assignees"),
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Remove an Assignee',
            },
        )
    )
    tags_add = forms.ModelMultipleChoiceField(
        # queryset=Task.tags.annotate(count=Count('taggit_taggeditem_items__id')).order_by('count', 'name'),
        queryset=_get_tags_qs(),
        required=False,
        label=_("Add Tags"),
        widget=AuthModelSelect2MultipleWidget(
            model=Tag,
            # queryset=_get_tags_qs(),  # Set in __init()__
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    tags_remove = forms.ModelMultipleChoiceField(
        # queryset=Task.tags.annotate(count=Count('taggit_taggeditem_items__id')).order_by('count', 'name'),
        queryset=_get_task_tags_qs(),
        required=False,
        label=_("Remove Tags"),
        widget=AuthModelSelect2MultipleWidget(
            model=Tag,
            # queryset=_get_task_tags_qs(),  # Set in __init()__
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    commodities_add = forms.ModelMultipleChoiceField(
        queryset=Commodity.objects.all(),
        required=False,
        label=_("Add Commodities"),
        widget=AuthModelSelect2MultipleWidget(
            model=Commodity,
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    commodities_remove = forms.ModelMultipleChoiceField(
        queryset=Commodity.objects.all(),
        required=False,
        label=_("Remove Commodities"),
        widget=AuthModelSelect2MultipleWidget(
            model=Commodity,
            # queryset=_get_task_tags_qs(),  # Set in __init()__
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    tips_commodity = forms.ModelChoiceField(
        queryset=Commodity.objects.all(),
        required=False,
        label=_("Tips Commodity"),
        widget=AuthModelSelect2Widget(
            model=Commodity,
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    categories_add = forms.ModelMultipleChoiceField(
        queryset=CustomerCategory.objects.all(),
        required=False,
        label=_("Add Categories"),
        widget=AuthModelSelect2MultipleWidget(
            model=CustomerCategory,
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    categories_remove = forms.ModelMultipleChoiceField(
        queryset=CustomerCategory.objects.all(),
        required=False,
        label=_("Remove Categories"),
        widget=AuthModelSelect2MultipleWidget(
            model=CustomerCategory,
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    status = forms.ChoiceField(
        choices=BLANK_CHOICE_DASH + Task.STATUS,
        required=False
    )
    priority = forms.ChoiceField(
        choices=BLANK_CHOICE_DASH + Task.PRIORITY,
        required=False
    )

    def __init__(self, tasks: QuerySet, *args, **kwargs):
        """
        Overridden constructor allowing passing of queryset for task
        choices.
        """
        self.helper = FormHelper()
        self.helper.form_tag = False
        super().__init__(*args, **kwargs)

        if tasks is not None and tasks.model is Task:
            self.fields['tasks'].queryset = tasks
            # Refresh the widget queryset since django-select2 does not allow choices or queryset
            # to be a runtime callable and the options may have changed since system start.
            self.fields['tags_add'].widget.queryset = _get_tags_qs()
            self.fields['tags_remove'].widget.queryset = _get_task_tags_qs()
        else:
            sentry_sdk.capture_message(f"Initializing a TaskBulkUpdateForm from a non-Task queryset: {tasks}")
            self.fields['tasks'].queryset = Task.objects.filter(
                pk__in=list(tasks.values_list('pk', flat=True)))

        self.helper.layout = Layout(
            Div(
                Div('status', 'priority', css_class="col-sm-3"),
                Div('assignees_add', 'assignees_remove', css_class="col-sm-3"),
                Div('tags_add', 'tags_remove', css_class="col-sm-3"),
                Div('categories_add', 'categories_remove', css_class="col-sm-3"),
                Div('commodities_add', 'commodities_remove', 'tips_commodity', css_class="col-sm-3"),
                css_class="row",
            ),
            FormActions(
                Submit('update', 'Apply', css_class='btn btn-primary'),
                StrictButton('Reset', id='reset-update-form', css_class='btn-secondary'),
                css_class='float-right'
            ),
        )

    def clean_tasks(self):
        """
        Implements requiring tasks whilst promoting the error message to
        a form error (as opposed to a field error).
        """
        data = self.cleaned_data['tasks']
        if not data:
            raise ValidationError(
                _('You must select at least 1 Task to update'))
        return data

    def clean(self):
        error_dict = {}
        # Make sure at least one task is selected
        if len(self.changed_data) <= 1 or 'tasks' not in self.changed_data:
            error_dict['tasks'] = ValidationError("You must select at least 1 Task and change at least one field for bulk updates.")

        # Don't allow the same tag to be added and removed
        if all(key in self.changed_data for key in ('tags_add', 'tags_remove'))\
           and all(key in self.cleaned_data for key in ('tags_add', 'tags_remove')):
            in_both = set(self.cleaned_data['tags_add']).intersection(self.cleaned_data['tags_remove'])
            if len(in_both) > 0:
                e = ValidationError(f"You cannot add and remove the same tags: {', '.join([t.name for t in in_both])}")
                error_dict['tags_add'] = e
                error_dict['tags_remove'] = e

        # Don't allow the same category to be added and removed
        if all(key in self.changed_data for key in ('categories_add', 'categories_remove'))\
           and all(key in self.cleaned_data for key in ('categories_add', 'categories_remove')):

            in_both = set(self.cleaned_data['categories_add']).intersection(self.cleaned_data['categories_remove'])
            if len(in_both) > 0:
                matched_names = [category.name for category in in_both]
                e = ValidationError(f"You cannot add and remove the same categories: {', '.join(list(matched_names))}")
                error_dict['categories_add'] = e
                error_dict['categories_remove'] = e

        # Don't allow the same assignee to be added and removed
        if all(key in self.changed_data for key in ('assignees_add', 'assignees_remove'))\
           and all(key in self.cleaned_data for key in ('assignees_add', 'assignees_remove')):

            in_both = set(self.cleaned_data['assignees_add']).intersection(self.cleaned_data['assignees_remove'])
            if len(in_both) > 0:
                matched_usernames = User.objects.filter(id__in=in_both).values_list('username', flat=True)
                e = ValidationError(f"You cannot add and remove the same assignees: {', '.join(list(matched_usernames))}")
                error_dict['assignees_add'] = e
                error_dict['assignees_remove'] = e

        # Don't allow the same commodity to be added and removed
        if all(key in self.changed_data for key in ('commodities_add', 'commodities_remove'))\
           and all(key in self.cleaned_data for key in ('commodities_add', 'commodities_remove')):
            in_both = set(self.cleaned_data['commodities_remove']).intersection(self.cleaned_data['commodities_remove'])
            if len(in_both) > 0:
                matched_names = [commodity.name for commodity in in_both]
                e = ValidationError(f"You cannot add and remove the same commodities: {', '.join(list(matched_names))}")
                error_dict['commodities_add'] = e
                error_dict['commodities_remove'] = e

        if error_dict:
            raise ValidationError(error_dict)
        return super().clean()


class TaskListFilterForm(forms.ModelForm):
    """ A search/filter form for tasks, primarily for the task list view.
    """
    EXTRA_STATUS_FILTERS = [("open", "All Open"), ("closed", "All Closed"), ("all", "All Tasks")]

    query_string_mapping = {
        'assignees': 'assignees__pk__in',
        'description': 'description__icontains',
        'name': 'customer__name__icontains',
        'phone': 'customer__phones__number__contains',
        'priority': 'priority',
        'tags': 'tags__pk__in',
        'created_from': 'created__gte',
        'created_to': 'created__lte',
        'last_updated_from': 'last_updated__gte',
        'last_updated_to': 'last_updated__lte',
        'border0': 'customer__border0__pk__in',
        'border1': 'customer__border1__pk__in',
        'gender': 'customer__sex'
    }
    assignees = forms.MultipleChoiceField(
        required=False,
        choices=_get_users,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by Assignee',
            },
        )
    )
    name = forms.CharField(
        label=_("Customer name"),
    )
    phone = forms.CharField(
        label=_("Customer phone"),
    )
    description = forms.CharField(
        label=_("Task description"),
    )
    created_from = forms.DateTimeField(
        label=_('Created from'),
        widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD hh:mm'}),
    )
    created_to = forms.DateTimeField(
        label=_('Created to'),
        widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD hh:mm'})
    )
    last_updated_from = forms.DateTimeField(
        label=_('Last update from'),
        widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD hh:mm'}),
    )
    last_updated_to = forms.DateTimeField(
        label=_('Last update to'),
        widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD hh:mm'})
    )
    border0 = forms.MultipleChoiceField(
        required=False,
        label=_("Customer country"),
        choices=get_border0_choices,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                # 'size': len(get_border0_choices()),
                'placeholder': 'Click here to filter by Country',
            },
        ),
    )
    border1 = forms.MultipleChoiceField(
        required=False,
        label=_("Customer county/region"),
        choices=_get_border1s,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by County/Region',
            },
        )
    )
    gender = forms.ChoiceField(
        required=False,
        label=_("Customer gender"),
        choices=(('', 'Any'), ('f', 'Female'), ('m', 'Male'))
    )
    tags = forms.ModelMultipleChoiceField(
        # queryset=Task.tags.annotate(count=Count('taggit_taggeditem_items__id')).order_by('count', 'name'),
        queryset=_get_task_tags_qs(),
        required=False,
        label=_("Associated Task Tags"),
        widget=AuthModelSelect2MultipleWidget(
            model=Tag,
            # queryset=_get_task_tags_qs(),  # Set in __init()__
            search_fields=['name__icontains'],
            max_results=200,
            attrs={
                'placeholder': 'Click here to filter by Tags',
                'data-minimum-input-length': 0,
            },
        )
    )
    complete_location = forms.ChoiceField(
        required=False,
        choices=(("ALL", BLANK_CHOICE_DASH),
                 ("Yes", _("Only customers with complete location details")),
                 ("No", _("Only customers without complete location details"))),
        initial='ALL',
        label=_("Has complete location details"),
    )
    # Don't use the ModelForm default or the field validator will
    # throw a ValidationError if the user selects one of the extra choices.
    status = forms.ChoiceField()

    class Meta:
        model = Task
        fields = ('assignees', 'description', 'priority', 'tags',)
        widgets = {
            'description': forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_id = "filter-form"
        self.helper.layout = Layout(
            Div(
                Div(
                    'name',
                    'phone',
                    'gender',
                    'border0',
                    'border1',
                    css_class="col-sm-4 border-right"
                ),
                Div(
                    'description', 'status', 'priority',
                    Div(
                        Div('created_from', css_class='col-sm-6'),
                        Div('created_to', css_class='col-sm-6'),
                        Div('last_updated_from', css_class='col-sm-6'),
                        Div('last_updated_to', css_class='col-sm-6'),
                        css_class="row"
                    ),
                    css_class="col-sm-4 border-right"
                ),
                Div(
                    'assignees',
                    'tags', 
                    'complete_location',
                    FormActions(
                        Submit('filter', 'Filter'),
                        StrictButton('Reset',
                                     id='reset-filter-form', css_class='btn-secondary'),
                        css_class='mt-auto ml-auto'
                    ),
                    css_class="col-sm-4 d-flex flex-column"
                ),
                css_class="row"
            ),
        )
        super().__init__(*args, **kwargs)

        added_choices = TaskListFilterForm.EXTRA_STATUS_FILTERS
        self.fields['status'].choices = (added_choices + Task.STATUS)
        status = self.fields['status']
        status.initial = 1

        self.fields['priority'].choices = (BLANK_CHOICE_DASH + Task.PRIORITY)
        priority = self.fields['priority']
        priority.initial = 1

        # Refresh the widget queryset since django-select2 does not allow choices or queryset
        # to be a runtime callable and the options may have changed since system start.
        # self.fields['tags'].choices = _get_task_tags()
        self.fields['tags'].widget.queryset = _get_task_tags_qs()

        # it's a search form, so we don't require anything
        for fieldname in self.fields:
            self.fields[fieldname].required = False


class TaskForm(forms.ModelForm):
    """ Form for the creation of Tasks.
    """
    # rendering all the customers on the page is too expensive. A subset of
    # customers rendered via the API based on user input.
    customer = forms.IntegerField()

    class Meta:
        model = Task
        fields = ('customer', 'status', 'priority', 'assignees', 'tags')
        widgets = {
        }

    def clean_customer(self):
        """ Converts value of customer `IntegerField` to a `Customer` instance.
        """
        pk = self.cleaned_data['customer']
        return Customer.objects.filter(pk=pk).first()


class TaskUpdateForm(TaskForm):
    """ Form for the modification of Tasks.
    """
    assignees = forms.MultipleChoiceField(
        required=False,
        choices=_get_active_users,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to select an Assignee',
            },
        ),
    )
    tags = forms.ModelMultipleChoiceField(
        # queryset=Task.tags.annotate(count=Count('taggit_taggeditem_items__id')).order_by('count', 'name'),
        queryset=_get_tags_qs(),
        required=False,
        label=_("Associated Task Tags"),
        widget=AuthModelSelect2MultipleWidget(
            model=Tag,
            # queryset=_get_task_tags_qs(),  # Set in __init()__
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )

    class Meta:
        model = Task
        fields = ('customer', 'status', 'priority', 'assignees', 'tags')
        widgets = {
        }

    def __init__(self, instance, *args, **kwargs):
        """ Overridden disable modification of Task.customer if there are any
        incoming or outgoing messages.
        """
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'customer', 'status', 'priority', 'assignees', 'tags',
            Submit('save', 'Save'),
        )

        super().__init__(instance=instance, *args, **kwargs)

        # Refresh the widget queryset since django-select2 does not allow choices or queryset
        # to be a runtime callable and the options may have changed since system start.
        self.fields['tags'].widget.queryset = _get_tags_qs()

        if (instance.outgoing_messages.exists()
                or instance.incoming_messages.exists()):
            self.fields['customer'].widget = forms.HiddenInput()


class TaskSMSReplyForm(SingleOutgoingSMSForm):

    sent_by_id = forms.IntegerField(widget=forms.HiddenInput())
    task = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        initial = kwargs.get('initial', {})
        task = initial.get('task')
        if task:
            customer = task.customer
        else:
            customer_id = initial.get('customer')  # the form view get_initial populates the customer_id in the 'customer' field
            try:
                customer = Customer.objects.get(pk=customer_id)
            except Customer.DoesNotExist:
                customer = None

        # If this form is being instantiated not as a result of data being posted (e.g. initial GET):
        if task is not None and customer is not None:
            self.fields['task'].initial = task.pk
            if hasattr(self, 'helper'):
                self.helper.form_method = 'POST'
                # / tasks / reply / custome.pk / task.pk /
                self.helper.form_action = reverse('task_reply', kwargs={'pk': customer.pk, 'task_pk': task.pk})

            if customer.border0 and customer.border3 is None:
                borderlevel1_name = BorderLevelName.objects.get(country=customer.border0.name, level=1).name
                borderlevel2_name = BorderLevelName.objects.get(country=customer.border0.name, level=2).name
                borderlevel3_name = BorderLevelName.objects.get(country=customer.border0.name, level=3).name
                self.fields[
                    'text'].initial = f'Dear farmer, to get accurate weather prediction and useful, timely farming tips, ' \
                                      f'SMS us your NAME, {borderlevel1_name.upper()}, {borderlevel3_name.upper()} and CROPS/LIVESTOCK you have, to 21606.'
        return

    def clean_task(self):
        """ Converts the integer primary key value to `Task` instance.
        """
        pk = int(self.cleaned_data['task'])

        try:
            return Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            raise ValidationError('Invalid Task id. Please try again.')

    def save(self, commit=True):
        sms = super().save(commit=False)

        task = self.cleaned_data['task']

        sms.sent_by_id = self.cleaned_data['sent_by_id']
        sms.message_type = OUTGOING_SMS_TYPE.TASK_RESPONSE
        sms.extra = {'task_id': task.id}
        sms.time_sent = now()
        sms.save()

        task.outgoing_messages.add(sms)

        return sms
