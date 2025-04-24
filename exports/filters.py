from django import forms
from django.utils.translation import gettext_lazy as _

import django_filters

from core.widgets import HTML5DateInput

from customers.models import Customer
from sms.models import IncomingSMS
from world.models import Border
from .form_helpers import CustomerExportFormHelper, IncomingSMSExportFormHelper


class CustomerExportFilterForm(forms.Form):

    incomplete_records = forms.BooleanField(
        label=_('Include incomplete records'),
        initial=True,
    )

    complete_record_filters = {
        'name__gt': '',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # if we don't remove the field the filterset will get an empty queryset
        # as this is not an actual field in the model.
        if args or kwargs.get('data'):
            self.fields.pop('incomplete_records')

    def get_complete_record_filters(self):
        if not self.data.get('incomplete_records', False):
            return self.complete_record_filters

        return {}

    def clean(self):
        cleaned_data = super().clean()
        complete_filters = self.get_complete_record_filters()
        if complete_filters:
            cleaned_data.update(complete_filters)

        cleaned_data.pop('incomplete_records', None)
        return cleaned_data


def get_county_choices():
    # TODO: i18n
    return list((county.id, county.name) for county in Border.kenya_counties)


class CustomerExportFilter(django_filters.FilterSet):

    name__gt = django_filters.CharFilter(
        widget=forms.HiddenInput()
    )
    # not DateFilters to avoid serialization issues with JSONField
    tasks__created__date__gte = django_filters.CharFilter(
        label=_("Task date range (start)"),
        help_text='Inclusive',
        widget=HTML5DateInput())
    tasks__created__date__lt = django_filters.CharFilter(
        label=_("Task date range (end)"),
        help_text='Exclusive',
        widget=HTML5DateInput())

    tasks__tags__name__in = django_filters.CharFilter(
        label=_("Task tag"),
        help_text='')

    county_id = django_filters.ChoiceFilter(
        label=_("County"),
        help_text='',
        choices=get_county_choices
    )

    postal_code = django_filters.CharFilter(
        label=_("Postal code"),
    )

    class Meta:
        model = Customer
        form = CustomerExportFilterForm
        fields = [
            'tasks__created__date__gte',
            'tasks__created__date__lt',
            'tasks__tags__name__in',
            'postal_code',
            'county_id',
            'name__gt',
        ]

    @property
    def qs(self):
        if not hasattr(self, '_qs'):
            self._qs = super().qs

            complete_filters = self.form.get_complete_record_filters()
            if complete_filters:
                self._qs = self._qs.filter(**complete_filters)

        return self._qs

    @property
    def form(self):
        """ Custom form property to enable use of django-crispy-forms.
        """
        if not hasattr(self, '_form'):
            self._form = super().form
            self._form.helper = CustomerExportFormHelper()

        return self._form


class IncomingSMSExportFilter(django_filters.FilterSet):

    # not DateFilters to avoid serialization issues with JSONField
    at__date__gte = django_filters.CharFilter(
        label=_("Date range (start)"),
        help_text='Inclusive',
        widget=HTML5DateInput())
    at__date__lt = django_filters.CharFilter(
        label=_("Date range (end)"),
        help_text='Exclusive',
        widget=HTML5DateInput())

    task__tags__name__in = django_filters.CharFilter(
        label=_("Task tag"),
        help_text='')

    customer__county_id = django_filters.ChoiceFilter(
        label=_("County"),
        help_text='',
        choices=get_county_choices
    )

    class Meta:
        model = IncomingSMS
        fields = [
            'at__date__gte',
            'at__date__lt',
            'task__tags__name__in',
            'customer__county_id'
        ]

    @property
    def form(self):
        """ Custom form property to enable use of django-crispy-forms.
        """
        if not hasattr(self, '_form'):
            self._form = super().form
            self._form.helper = IncomingSMSExportFormHelper()

        return self._form
