from django import forms
from django.core.exceptions import ValidationError
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Layout, Submit
from phonenumber_field.formfields import PhoneNumberField

from core.widgets import HTML5DateInput
from customers.models import Customer

from .models import FreeSubscriptionOffer, VerifyInStoreOffer, Voucher


class FreeSubscriptionOfferForm(forms.ModelForm):

    class Meta:
        model = FreeSubscriptionOffer
        fields = ('name', 'expiry_date', 'months', )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div('name', css_class='col-md-12'),
            Div(Div('expiry_date', css_class='col-md-6'),
                Div('months', css_class='col-md-6')),
            FormActions(
                Submit('submit', 'Submit',
                       css_class='btn btn-primary col-md-offset-11'))
        )
        super().__init__(*args, **kwargs)
        self.fields['expiry_date'].widget = HTML5DateInput()


class VerifyInStoreOfferForm(forms.ModelForm):

    class Meta:
        model = VerifyInStoreOffer
        fields = ('name', 'expiry_date', 'message', 'confirmation_message', )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div('name', 'expiry_date', css_class='col-md-6'),
            Div('message', 'confirmation_message', css_class='col-md-6'),
            FormActions(
                Submit('submit', 'Submit',
                       css_class='btn btn-primary col-md-offset-11')
            )
        )
        super().__init__(*args, **kwargs)
        self.fields['expiry_date'].widget = HTML5DateInput()


class GenerateVouchersForm(forms.Form):

    number_to_generate = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = 'form-inline'
        self.helper.field_template = 'bootstrap3/layout/inline_field.html'
        self.helper.layout = Layout(
            'number_to_generate',
            FormActions(
                Submit('submit', 'Generate', css_class='btn btn-primary')
            )
        )
        super().__init__(*args, **kwargs)


class OfferVerifyForm(forms.Form):
    """ Form for verifying that an offer exists and hasn't been used.
    """
    code = forms.CharField(label=_('Voucher code'), max_length=100)
    phone = PhoneNumberField(label=_('Phone number'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal col-md-offset-2'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-4'
        self.helper.layout = Layout(
            Div(
                Field('code', data_placeholder="Voucher code"),
                Field('phone', data_placeholder="+2547000000000")
            ),
            FormActions(
                Submit('submit', 'Verify',
                       css_class='btn btn-primary btn-block')
            )
        )

    def clean_code(self):
        """ Validates the voucher code exists, the associated offer has not
        expired, and the voucher has not been previously used.
        """
        code = self.cleaned_data['code']
        voucher = Voucher.objects.filter(code=code).first()

        if not voucher:
            raise ValidationError(_(
                "The voucher %(code)s does not exist."),
                params={'code': code})

        if not voucher.offer.is_current(localtime(now()).date()):
            raise ValidationError(_(
                "The voucher %(code)s has expired."),
                params={'code': code})

        if voucher.used_by:
            raise ValidationError(_(
                "The voucher %(code)s has already been used."),
                params={'code': code})

        return code

    def clean_phone(self):
        """ Validates that the entered phone number matches an existing
        customer.
        """
        phone = self.cleaned_data['phone']
        if not Customer.objects.filter(phones__number=phone).exists():
            raise ValidationError(_(
                "%(phone)s does not correspond to an existing customer."),
                params={'phone': phone})

        return phone
