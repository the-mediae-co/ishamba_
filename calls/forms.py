from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Layout, Submit

from calls.models import CallCenterPhone, PusherSession


class ChoosePhoneForm(forms.Form):
    phone = forms.ModelChoiceField(
        queryset=CallCenterPhone.objects.filter(is_active=True),
        help_text=_('Please select the phone number you are using'))
    connect_anyway = forms.BooleanField(
        help_text=_('Check this to connect even if there are active sessions '
                    'with your username/phone.'),
        required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div('phone', 'connect_anyway'),
            FormActions(Submit('submit', 'OK',
                        css_class='btn btn-primary float-right'))
        )

        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()

        # Check if user has active connection
        user = self.request.user

        if data.get('connect_anyway'):  # Don't do checks
            return data

        try:
            latest_user_session = PusherSession.objects.filter(operator=user).latest('created_on')
        except PusherSession.DoesNotExist:
            pass
        else:
            if not latest_user_session.finished_on and latest_user_session.pusher_session_key:
                raise forms.ValidationError(
                    _("You have already connected to the call center! Please "
                      "close all browser windows and try again."))

            phone = data.get('phone')
            if (PusherSession.objects.connected()
                                     .filter(call_center_phone=phone)
                                     .exists()):
                raise forms.ValidationError(
                    _("There is another user already connected with this "
                      "phone!"))

        return data
