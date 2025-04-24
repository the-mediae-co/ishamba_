from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Div, Field, Layout, Submit
from django_select2 import forms as s2forms
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers import NumberParseException
from taggit.models import Tag

from agri.models.base import Commodity
from callcenters.models import CallCenterSender
from core.constants import LANGUAGES
from core.widgets import AuthModelSelect2MultipleWidget
from customers.models import CustomerCategory, CustomerPhone
from sms.constants import (GSM_EXTENDED_SET, GSM_WHITELIST, KENYA_COUNTRY_CODE,
                           MAX_SMS_LEN, UGANDA_COUNTRY_CODE,
                           ZAMBIA_COUNTRY_CODE)
from sms.models import IncomingSMS, OutgoingSMS
from tasks.models import Task
from world.utils import (get_border0_choices, get_border1_choices,
                         get_border2_choices, get_border3_choices)


class SingleOutgoingSMSForm(forms.ModelForm):
    gsm_charset = forms.CharField(initial=GSM_WHITELIST + GSM_EXTENDED_SET,
                                  widget=forms.HiddenInput(),
                                  required=False)
    countries = forms.CharField(initial=[],
                                widget=forms.HiddenInput(),
                                required=False)

    class Meta:
        model = OutgoingSMS
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={'cols': 80, 'rows': 4}),
        }
        help_texts = {
            'text': _('NOTE: The following characters count as two in SMS messages: ~€^{}[]\\|'),
        }

    def __init__(self, *args, **kwargs):
        call_center = kwargs.pop("call_center", None)
        super().__init__(*args, **kwargs)
        data = kwargs.get('initial')
        if not data:
            data = kwargs.get('data')
        if data is not None:
            countries = data.get('countries', [])
            if isinstance(countries, str):
                countries = eval(countries)
        else:
            countries = []
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'gsm_charset',
            'countries',
            'text',
            HTML("""
                 <div class="character-counter">
                    <span id="counter">One message: 160 characters remaining</span>
                 </div>
                 <div class="illegal-gms-character">
                    <span id="illegal-character"></span>
                 </div>
                 """),
        )
        if call_center:
            self.fields['senders'] = forms.ChoiceField(choices=[(cc.sender_id, cc.sender_id) for cc in call_center.senders.all()],
                                                                    label=_('Sender for %s recipients' % call_center.name),
                                                                    required=True)
        else:
            self.fields['senders'] = forms.ChoiceField(choices=[(cs.sender_id, cs.sender_id) for cs in CallCenterSender.objects.all()],
                                                                    label="Senders",
                                                                    required=True)
        self.helper.layout.append('senders')

        self.helper.layout.extend([
            HTML("""
                 <div class="multiple-gsm-pages">
                    <span id="allow-multiple-pages"></span>
                 </div>
                 """),
            FormActions(
                Submit('submit', 'Send', css_class='btn btn-primary')
            )
        ])


class BulkOutgoingSMSForm(forms.ModelForm):
    send_at = forms.DateTimeField(label=_("Send at"),
                                  help_text=_("Optionally specify when to send the message (local time zone)"),
                                  widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD HH:MM'}),
                                  required=False)
    gsm_charset = forms.CharField(initial=GSM_WHITELIST + GSM_EXTENDED_SET,
                                  widget=forms.HiddenInput(),
                                  required=False)
    countries = forms.CharField(initial=[],
                                widget=forms.HiddenInput(),
                                required=False)

    class Meta:
        model = OutgoingSMS
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={'cols': 80, 'rows': 4}),
        }
        help_texts = {
            'text': _('NOTE: The following characters count as two in SMS messages: ~€^{}[]\\|'),
        }

    def __init__(self, *args, **kwargs):
        call_center = kwargs.pop("call_center", None)
        super().__init__(*args, **kwargs)
        data = kwargs.get('initial')
        if not data:
            data = kwargs.get('data')
        countries = data.get('countries')
        if isinstance(countries, str):
            countries = eval(countries)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'gsm_charset',
            'countries',
            'text',
            HTML("""
                 <div class="character-counter">
                    <span id="counter">One message: 160 characters remaining</span>
                 </div>
                 <div class="illegal-gms-character">
                    <span id="illegal-character"></span>
                 </div>
                 """),
        )

        if call_center:
            self.fields['senders'] = forms.ChoiceField(choices=[(cc.sender_id, cc.sender_id) for cc in call_center.senders.all()],
                                                                    label=_('Sender for %s recipients' % call_center.name),
                                                                    required=True)
        else:
            self.fields['senders'] = forms.ChoiceField(choices=[(cs.sender_id, cs.sender_id) for cs in CallCenterSender.objects.all()],
                                                                    label="Senders",
                                                                    required=True)
        self.helper.layout.append('senders')

        self.helper.layout.extend([
            'send_at',
            HTML("""
                 <div class="multiple-gsm-pages">
                    <span id="allow-multiple-pages"></span>
                 </div><br>
                 """),
            FormActions(
                Submit('submit', 'Send', css_class='btn btn-primary')
            )
        ])

        self.count = MAX_SMS_LEN  # Used to prime the ajax count field


class MultiplePhoneNumberField(forms.Field):
    widget = forms.Textarea

    def to_python(self, value):
        if not value:
            return None

        lines = value.strip().splitlines(False)
        numbers = []
        invalid_numbers = []
        for line in lines:
            if not line.strip():
                continue

            try:
                number = PhoneNumber.from_string(line.strip())
            except NumberParseException:
                invalid_numbers.append(line)
            else:
                if number.is_valid():
                    numbers.append(number)
                else:
                    invalid_numbers.append(line)

        if invalid_numbers:
            raise ValidationError('The following numbers are not valid: {}'.format(', '.join(invalid_numbers)))
        return numbers

    def clean(self, value):
        numbers = self.to_python(value)
        self.validate(value)
        return numbers


class CustomerFilterForm(forms.Form):
    """
    A search/filter form for customers, primarily for bulk SMS sending.
    """
    query_string_mapping = {
        'phones': 'phones__in',
        'border0': 'border0__pk__in',
        'border1': 'border1__pk__in',
        'border2': 'border2__pk__in',
        'border3': 'border3__pk__in',
        'commodities_farmed': 'commodities__in',
        'tip_subscriptions': 'tip_subscriptions',
        'categories': 'categories__in',
        'lat': 'lat',
        'lng': 'lng',
        'distance_range': 'distance_range',
        'preferred_language': 'preferred_language__in',
        'can_access_call_centre': 'can_access_call_centre',
        'premium_subscriber': 'premium_subscriber',
        'has_electricity': 'has_electricity',
        'has_irrigation_water': 'has_irrigation_water',
        'task_tags': 'task_tags',
        'missing_location': 'location__isnull',
        'gender': 'gender',
    }

    phones = forms.ModelMultipleChoiceField(
        queryset=CustomerPhone.objects.order_by('number'),
        required=False,
        label=_("Specific phone numbers"),
        widget=AuthModelSelect2MultipleWidget(
            model=CustomerPhone,
            queryset=CustomerPhone.objects.order_by('number'),
            search_fields=['number__contains'],
            max_results=100,
            attrs={'data-minimum-input-length': 3},
        )
    )
    gender = forms.ChoiceField(
        required=False,
        choices=(("", "All customers"),
                 ("f", "Only Females"),
                 ("m", "Only Males"),
                 ("u", "Only Unknown")),
        initial='',
        label=_("Gender"),
    )
    border0 = forms.MultipleChoiceField(
        required=False,
        label=_("Country"),
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
        label=_("County/Region"),
        choices=get_border1_choices,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by County/Region',
            },
        )
    )
    border2 = forms.MultipleChoiceField(
        required=False,
        label=_("Subcounty/District"),
        choices=get_border2_choices,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by Subcounty/District',
            },
        )
    )
    border3 = forms.MultipleChoiceField(
        required=False,
        label=_("Ward/County"),
        choices=get_border3_choices,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by Ward/County',
            },
        )
    )
    preferred_language = forms.MultipleChoiceField(
        choices=[lang for lang in LANGUAGES.choices if lang[0] != None],
        required=False,
        label=_("Preferred Language"),
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by language',
            },
        )
    )
    commodities_farmed = forms.ModelMultipleChoiceField(
        queryset=Commodity.objects.order_by(Lower('name')),
        required=False,
        label=_("Commodities Farmed"),
        widget=AuthModelSelect2MultipleWidget(
            model=Commodity,
            queryset=Commodity.objects.order_by(Lower('name')),
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    tip_subscriptions = forms.ModelMultipleChoiceField(
        queryset=Commodity.objects.order_by(Lower('name')),
        required=False,
        label=_("Tip subscriptions"),
        widget=AuthModelSelect2MultipleWidget(
            model=Commodity,
            queryset=Commodity.objects.order_by(Lower('name')),
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=CustomerCategory.objects.order_by(Lower('name')),
        required=False,
        label=_("Categories"),
        widget=AuthModelSelect2MultipleWidget(
            model=CustomerCategory,
            queryset=CustomerCategory.objects.order_by(Lower('name')),
            search_fields=['name__icontains'],
            max_results=300,
            attrs={'data-minimum-input-length': 0},
        )
    )
    can_access_call_centre = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Only customers who can access call centre")
    )
    premium_subscriber = forms.ChoiceField(
        required=False,
        choices=(("ALL", "All customers"),
                 ("Yes", "Premium only"),
                 ("No", "Non-premium only")),
        initial='ALL',
        label=_("Premium subscribers"),
    )
    lat = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(),
    )
    lng = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(),
    )
    distance_range = forms.IntegerField(
        required=False,
        label=_("Distance (km)"),
        help_text=_("From the blue marker location on the map above")
    )
    missing_location = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Only customers without location details")
    )
    task_tags = forms.ModelMultipleChoiceField(
        # queryset=Task.tags.annotate(count=Count('taggit_taggeditem_items__id')).order_by('count', 'name'),
        queryset=Task.tags.order_by(Lower('name')),
        required=False,
        label=_("Associated Task Tags"),
        widget=AuthModelSelect2MultipleWidget(
            model=Tag,
            queryset=Task.tags.order_by(Lower('name')),
            search_fields=['name__icontains'],
            max_results=200,
            attrs={'data-minimum-input-length': 0},
        )
    )
    has_electricity = forms.ChoiceField(
        required=False,
        choices=(("ALL", "All customers"),
                 ("Yes", "Has electricity"),
                 ("No", "No electricity")),
        initial='ALL',
        label=_("Electricity"),
    )
    has_irrigation_water = forms.ChoiceField(
        required=False,
        choices=(("ALL", "All customers"),
                 ("Yes", "Has access to water for irrigation"),
                 ("No", "No access to water for irrigation")),
        initial='ALL',
        label=_("Irrigation Water"),
    )

    def __init__(self, *args, **kwargs):
        form_action = kwargs.pop('action', None)
        form_button_text = kwargs.pop('button_text', 'Submit')
        call_center = kwargs.pop("call_center", None)
        super().__init__(*args, **kwargs)
        # Refresh the choices since django-select2 does not allow choices or queryset
        # to be a runtime callable and the options may have changed since system start.
        self.fields['categories'].queryset = CustomerCategory.objects.order_by(Lower('name'))
        self.fields['categories'].widget.queryset = CustomerCategory.objects.order_by(Lower('name'))
        self.fields['commodities_farmed'].queryset = Commodity.objects.order_by(Lower('name'))
        self.fields['commodities_farmed'].widget.queryset = Commodity.objects.order_by(Lower('name'))
        self.fields['task_tags'].queryset = Task.tags.order_by(Lower('name'))
        self.fields['task_tags'].widget.queryset = Task.tags.order_by(Lower('name'))

        # if 'data' not in kwargs:
            # If this form is not being created as a result of an http post with data.
            # I.e. this is the empty form initialization
            # Initially, only populate the County field. The following queries can
            # be slow and are unnecessary with the ajax UI working.
            # self.fields['border1'].queryset = Border.objects.none()
            # self.fields['border2'].queryset = Border.objects.none()
            # self.fields['border3'].queryset = Border.objects.none()

            # self.fields['border0'].widget.attrs.update({'hidden': True})
            # self.fields['border1'].disabled = True
            # self.fields['border1'].widget.is_hidden = True
            # self.fields['border1'].widget.attrs.update({'hidden': True})
            # self.fields['border2'].disabled = True
            # self.fields['border2'].widget.is_hidden = True
            # self.fields['border2'].widget.attrs.update({'hidden': True})
            # self.fields['border3'].disabled = True
            # self.fields['border3'].widget.is_hidden = True
            # self.fields['border3'].widget.attrs.update({'hidden': True})

        self.helper = FormHelper(self)
        self.helper.attrs = {'id': 'updates_form'}  # Add an HTML ID for the updates_form so jquery can find it
        if form_action:
            self.helper.form_action = form_action

        # Seed the initial ajax customer count field by counting number of unique
        # customers with main numbers in our operating countries. Retrieve only
        # their ID, to speed django performance considerably.

        phones = CustomerPhone.objects.filter(
            customer__has_requested_stop=False,
            is_main=True,
        ).filter(
            Q(number__startswith=f"+{KENYA_COUNTRY_CODE}") |
            Q(number__startswith=f"+{UGANDA_COUNTRY_CODE}") |
            Q(number__startswith=f"+{ZAMBIA_COUNTRY_CODE}")
        )
        if call_center:
            border_query = f'customer__border{call_center.border.level}'
            phones = phones.filter(**{border_query: call_center.border.id})
        self.count = len(set(phones.values_list('id', flat=True)))

        self.helper.layout = Layout(
            Div(Field('lng', 'lat')),
            Div(HTML('<div id="map" style="height: 360px;"></div>'), css_class="col-md-12"),
            Div(
                Div(
                    'distance_range',
                    Field('missing_location'),
                    HTML("<hr>"),
                    Field('border0'),
                    Field('border1'),
                    Field('border2'),
                    Field('border3'),
                    HTML("<hr>"),
                    Field('commodities_farmed'),
                    Field('tip_subscriptions'),
                    Field('categories'),
                    Field('task_tags'),
                    Field('has_electricity'),
                    Field('has_irrigation_water'),
                    css_class="col-md-6"
                ),
                Div(
                    Div(
                        Div(
                            'phones',
                            Field('premium_subscriber'),
                            Field('gender'),
                            Field('preferred_language'),
                            HTML("<hr>")
                        ),
                        # css_class="row"
                    ),
                    Div(
                        Div(
                            HTML("""
                                <p id="customer-count">
                                {% include 'sms/includes/customer_count.html' %}
                                </p>
                                """),
                            css_class="col-md-6"
                        ),
                        Div(
                            Submit('submit', form_button_text,
                                   css_class='btn btn-primary btn-lg float-right'),
                            css_class="col-md-6"
                        ),
                        css_class="row no-gutters"
                    ),
                    css_class="col-md-6"
                ),
                css_class="row",
            ),
        )


class BaseIncomingSMSForm(forms.ModelForm):
    """
    Base form for accepting POST requests from SMS gateways as a callback upon
    receiving messages.
    """
    FIELD_NAME_MAPPING = {
    }

    class Meta:
        model = IncomingSMS
        fields = ('at', 'text', 'sender', 'recipient', 'gateway_id')

    def add_prefix(self, field_name):
        """
        Looks up the field name in the `FIELD_NAME_MAPPING` dict and translates
        the field name if required.
        """
        field_name = self.FIELD_NAME_MAPPING.get(field_name, field_name)
        return super(BaseIncomingSMSForm, self).add_prefix(field_name)
