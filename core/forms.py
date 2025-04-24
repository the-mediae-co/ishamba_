from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, HTML, Layout, Submit

from core import constants
from core.widgets import HTML5DateInput
from callcenters.models import CallCenter


class DateRangeForm(forms.Form):
    start_date = forms.DateField(localize=True, widget=HTML5DateInput())
    end_date = forms.DateField(localize=True, widget=HTML5DateInput())

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Div('start_date', 'end_date', css_class='customer-columns'),
            FormActions(
                Submit('submit', 'Update'),
                # Unfortunately, crispyforms doesn't handle a form submit element without class = btn-primary
                # so we can't style the export button as secondary. The work-around is to insert raw HTML.
                HTML("""
                <input type="submit" name="export" value="Export CSV" class="btn btn-secondary" id="button-id-export">
                """),
                # Button('export', 'Export CSV', css_class='btn btn-secondary'),
            )
        )
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get('start_date') and data.get('end_date'):
            try:
                assert(data['start_date'] <= data['end_date'])
            except AssertionError:
                raise forms.ValidationError(mark_safe('End date must be &ge; start date.'), code='date order')
        return data

class MetricsForm(DateRangeForm):
    call_center = forms.ModelChoiceField(queryset=CallCenter.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            Div('start_date', 'end_date', css_class='customer-columns'),
            Div('call_center'),
            FormActions(
                Submit('submit', 'Update'),
                # Unfortunately, crispyforms doesn't handle a form submit element without class = btn-primary
                # so we can't style the export button as secondary. The work-around is to insert raw HTML.
                HTML("""
                <input type="submit" name="export" value="Export CSV" class="btn btn-secondary" id="button-id-export">
                """),
                # Button('export', 'Export CSV', css_class='btn btn-secondary'),
            )
        )


class DateResolutionForm(DateRangeForm):
    date_resolution = forms.ChoiceField(choices=constants.DATE_RESOLUTION_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            Div(
                Div('start_date', css_class='col-md-4'),
                Div('end_date', css_class='col-md-4'),
                Div('date_resolution', css_class='col-md-4'),
                css_class='row'),
            FormActions(
                Submit('submit', 'Update', css_class='btn btn-primary')
            )
        )


class DateResolutionWithMembershipForm(DateResolutionForm):
    include_inactive_customers = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            Div(
                Div('start_date', 'end_date', css_class='col-md-6'),
                Div('date_resolution', 'include_inactive_customers',
                    css_class='col-md-6'),
                css_class='row'),
            FormActions(
                Submit('submit', 'Update', css_class='btn btn-primary')
            )
        )


class SelectWithData(forms.Select):
    extra_attrs = None

    def optgroups(self, name, value, attrs=None):
        values, labels, choice_attrs = [], [], []
        for choice in self.choices:
            values.append(choice[0])
            labels.append(choice[1])
            try:
                choice_attrs.append(choice[2])
            except IndexError:
                choice_attrs.append({})

        self.choices = zip(values, labels)
        self.extra_attrs = choice_attrs

        return super().optgroups(name, value, attrs=attrs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=None, attrs=None)
        if self.extra_attrs:
            option['attrs'].update(self.extra_attrs[index])
        return option
