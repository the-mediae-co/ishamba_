from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Layout, Submit
from callcenters.models import CallCenter, CallCenterOperator


class ChooseCallCenterForm(forms.Form):
    call_center = forms.ModelChoiceField(
        queryset=CallCenter.objects.none(),
        help_text=_('Please select to switch your current call center'))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        user = self.request.user
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div('call_center'),
            FormActions(Submit('submit', 'OK',
                        css_class='btn btn-primary float-right'))
        )
        super().__init__(*args, **kwargs)
        current_call_center = CallCenterOperator.objects.filter(
            operator=user, active=True
        ).order_by('-current', '-id').first()
        queryset = CallCenter.objects.filter(
            call_center_operators__operator=user
        )
        if current_call_center:
            queryset = queryset.exclude(id=current_call_center.call_center_id)

        self.fields['call_center'].queryset = queryset
