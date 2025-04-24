import phonenumbers

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.contrib.gis.forms.widgets import BaseGeometryWidget
from django.db.models.functions import Lower
from django.db.models import BLANK_CHOICE_DASH, Value
from django.db.models.functions import Concat
from django.utils.functional import cached_property
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _

from crispy_forms.bootstrap import FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Fieldset, Layout, Submit, HTML
from django_select2 import forms as s2forms

from agri import forms as agri_forms
from agri.constants import SUBSCRIPTION_FLAG
from agri.models.base import Commodity
from core.widgets import AuthModelSelect2Widget, AuthModelSelect2MultipleWidget
from core.constants import SEX
from customers.models import (Customer, CustomerCategory, CustomerPhone, CropHistory,
                              CustomerQuestionAnswer, CustomerCommodity)
from markets.models import Market, MarketSubscription
from world.utils import point_in_supported_area, get_border0_choices, get_border1_choices
from world.models import Border
from tips import forms as tip_forms


class MarketModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.is_main_market:
            return "{} (main market)".format(obj.name)
        return obj.name


# noinspection PyPep8Naming
def CustomerForm(border_menu_labels: dict, *args, **kwargs) -> forms.ModelForm:
    """
    A bit of a hack, but we need to create the CustomerForm Meta class
    dynamically so that the administrative boundary names can be based
    on the country in which the customer resides. The border_menu_labels
    is passed into the inner class's 'labels' field of the meta class.
    https://stackoverflow.com/questions/297383/dynamically-update-modelforms-meta-class
    https://stackoverflow.com/questions/36152754/dynamically-update-modelforms-meta-class-fields-using-views
    """
    class MyCustomerForm(forms.ModelForm):
        # phones = forms.CharField(help_text=_('If customer has multiple phone numbers, enter their main number '
        #                                      'first and separate each with commas. E.g. +254720123456,+25472013579'))
        phones = forms.CharField()
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
        commodities = forms.ModelMultipleChoiceField(
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

        class Meta:
            model = Customer
            fields = ('name', 'phones', 'dob', 'sex', 'relationship_status',
                      'id_number', 'location', 'postal_address', 'postal_code',
                      'border0', 'border1', 'border2', 'border3', 'village',
                      'agricultural_region', 'commodities', 'preferred_language',
                      'categories', 'phone_type', 'farm_size', 'notes',
                      'has_requested_stop', )
            widgets = {'location': BaseGeometryWidget({'map_srid': 4326}),
                       'postal_address': forms.Textarea(attrs={'rows': 4, 'cols': 20}),
                       'notes': forms.Textarea(attrs={'rows': 8, 'cols': 40}),
                       }
            labels = border_menu_labels

        def __init__(self, *args, **kwargs):
            self.helper = FormHelper()
            self.helper.form_tag = False  # The html template has the form tags, so we don't need crispy to add them
            classes = 'col-md-6'
            self.helper.layout = Layout(
                Div(
                    Div('name', css_class='col-md-3'),
                    Div('phones', css_class='col-md-4'),
                    Div(HTML("""<small>
                         If the customer has multiple phone numbers, enter their main number
                         first and separate each with commas. E.g. +254720123456,+25472013579
                         </small>"""), css_class='col-md-5'),
                    css_class='row'
                ),
                Div(
                    Div(Field('dob', placeholder="DD/MM/YYYY"), css_class='col-md-3'),
                    Div('sex', css_class='col-md-3'),
                    Div('phone_type', css_class='col-md-3'),
                    css_class='row'
                ),
                Div(
                    Div('relationship_status', css_class='col-md-3'),
                    Div('id_number', css_class='col-md-3'),
                    Div('preferred_language', css_class='col-md-3'),
                    css_class='row'
                ),
                Div(
                    Div('has_requested_stop', css_class='col-md-3'),
                    css_class='row'
                ),
                Div(
                    Div(
                        css_id='map',
                        css_class='col-md-12',
                        style='height: 360px;',
                    ), css_class='row',
                ),
                Div(
                    Div('border0', 'border1', 'border2', 'border3', css_class='col-md-6'),
                    Div('postal_address', 'village', 'postal_code', css_class='col-md-6'),
                    css_class='row'
                ),
                Div(
                    Div('commodities', css_class='col-md-6'),
                    Div('agricultural_region', 'farm_size', css_class='col-md-6'),
                    css_class='row'
                ),
                Fieldset(
                    'Extras',
                    Div(
                        Div(
                            Field('categories'),
                            css_class='col-md-6'
                        ),
                        Div('notes', css_class=classes),
                        css_class='row'
                    )
                )
            )
            super().__init__(*args, **kwargs)
            self.fields['border0'].queryset = Border.objects.filter(level=0)

            # Refresh the choices since django-select2 does not allow choices or queryset
            # to be a runtime callable and the options may have changed since system start.
            self.fields['categories'].queryset = queryset = CustomerCategory.objects.order_by(Lower('name'))
            self.fields['categories'].widget.queryset = queryset = CustomerCategory.objects.order_by(Lower('name'))
            self.fields['commodities'].queryset = queryset = Commodity.objects.order_by(Lower('name'))
            self.fields['commodities'].widget.queryset = queryset = Commodity.objects.order_by(Lower('name'))

            if 'instance' in kwargs and kwargs['instance'] is not None:
                # If editing (displaying) or updating an existing customer
                customer = kwargs['instance']

                if self.has_changed() and self.is_valid():
                    # This is a customer update (saving new data) or ajax update (update menu states)
                    border0 = self.cleaned_data.get('border0')
                    border1 = self.cleaned_data.get('border1')
                    border2 = self.cleaned_data.get('border2')
                    if border0:
                        # The border1 menu will be enabled, so add a queryset
                        self.fields['border1'].queryset = Border.objects.filter(level=1, parent=border0).order_by('name')
                    if border1:
                        # The border2 menu will be enabled, so add a queryset
                        self.fields['border2'].queryset = Border.objects.filter(level=2, parent=border1).order_by('name')
                    if border2:
                        # The border3 menu will be enabled, so add a queryset
                        self.fields['border3'].queryset = Border.objects.filter(level=3, parent=border2).order_by('name')
                else:
                    # This is a customer edit request (display customer data in form fields) or ajax menu update
                    if customer.border0:
                        # The border1 menu will be enabled, so add a queryset
                        self.fields['border1'].queryset = Border.objects.filter(level=1, parent=customer.border0).order_by('name')
                    if customer.border1:
                        # The border2 menu will be enabled, so add a queryset
                        self.fields['border2'].queryset = Border.objects.filter(level=2, parent=customer.border1).order_by('name')
                    if customer.border2:
                        # The border3 menu will be enabled, so add a queryset
                        self.fields['border3'].queryset = Border.objects.filter(level=3, parent=customer.border2).order_by('name')

            elif 'data' not in kwargs:
                # If this is the empty form initialization...
                # Initially, only populate the Country field. The following queries can
                # be slow and are unnecessary with the ajax UI working.
                self.fields['border1'].queryset = Border.objects.none()
                self.fields['border2'].queryset = Border.objects.none()
                self.fields['border3'].queryset = Border.objects.none()

        def clean_location(self):
            location = self.cleaned_data['location']
            if location and not point_in_supported_area(location):
                raise ValidationError('Location is not in a supported area')
            return location

        def clean_phones(self):
            phones = []
            if 'phones' in self.cleaned_data:
                # First verify that all phone numbers are valid
                phones_str = self.cleaned_data.get('phones')
                phone_strs = phones_str.split(',')
                for phone_str in phone_strs:
                    if len(phone_str.strip()) == 0:
                        continue
                    try:
                        phone = phonenumbers.parse(phone_str, None)
                        # Ignore the temporary fake '+245' phone numbers used for duplicate farmers.
                        # Validate the rest.
                        if not phone_str.startswith('+245') and not phonenumbers.is_valid_number(phone):
                            raise ValidationError(f'{phone_str} is not a valid phone number')
                        phones.append(phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164))
                    except phonenumbers.NumberParseException:
                        raise ValidationError(f'{phone_str} is not a valid phone number')

                # Then make sure they don't belong to a different user
                existing = CustomerPhone.objects.filter(number__in=phones).exclude(customer_id=self.instance.id)
                if existing.exists():
                    existing_numbers = ','.join(list(existing.values_list('number', flat=True)))
                    if existing.count() > 1:
                        error_str = f"{existing_numbers} already belong to other customers."
                    else:
                        error_str = f"{existing_numbers} already belongs to another customer."
                    raise ValidationError(error_str)
            if len(phones) > 0:
                return phones
            else:
                raise ValidationError(f'Customer must have at least one phone number')

    return MyCustomerForm(*args, **kwargs)


class CustomerQuestionAnswerForm(forms.ModelForm):
    class Meta:
        model = CustomerQuestionAnswer
        fields = ('question', 'text',)

    def __init__(self, question=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.html5_required = False

        self.fields['text'].required = False
        if question is not None:
            choices = question.get_choices()
            if choices:
                self.fields['text'].widget = forms.widgets.Select(choices=choices)

    def has_changed(self):
        changed = super().has_changed()
        if not changed and self.instance.pk is None:
            return True
        return changed


class CustomerQuestionAnswerFormset(forms.BaseInlineFormSet):

    def get_form_kwargs(self, i, question):
        kwargs = self.form_kwargs.copy()
        if question:
            kwargs['initial'] = {'question': question.pk}
        return kwargs

    def get_questions(self):
        from customers.models import CustomerQuestion
        if not hasattr(self, '_questions'):
            self._questions = CustomerQuestion.objects.all()
        return self._questions

    @cached_property
    def forms(self):
        questions = self.get_questions()
        forms = []
        for idx, question in enumerate(questions):
            form = self._construct_form(idx, **self.get_form_kwargs(idx, question))
            forms.append(form)
        return forms

    def total_form_count(self):
        return self.get_questions().count()

    @property
    def empty_form(self):
        questions = self.get_questions()
        form = self.form(
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
            use_required_attribute=False,
            **self.get_form_kwargs(None, questions.first())
        )
        self.add_fields(form, None)
        return form


class CustomerQuestionAnswerFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False

        self.layout = Layout(
            Div(
                Field("question", template="customers/partials/question-field.html"),
                Field("text", template="customers/partials/answer-field.html"),
                css_class="col-md-6 question"
            ),
        )


class CustomerMarketForm(forms.ModelForm):
    class Meta:
        model = MarketSubscription
        fields = ('market', 'backup')
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': "A customer can only be subscribed to each market once",
            }
        }

    market = MarketModelChoiceField(
        Market.objects.all())
    backup = MarketModelChoiceField(
        Market.objects.filter(is_main_market=True), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.html5_required = False


class CustomerMarketFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False

        self.layout = Layout(
            Div(
                Div(Div("market", css_class="col-md-6"),
                    Div("backup", css_class="col-md-6"),
                    css_class="col-md-12 panel-field-container"),
                css_class="row card mod-market-subscription"
            ),
        )


def _get_categories():
    return CustomerCategory.objects.order_by(Lower('name')).values_list('pk', 'name')


def _get_users():
    return User.objects.order_by('-is_active', 'username').values_list('pk', 'username')


def _get_border1s():
    border1_qs = Border.objects.filter(level=1) \
        .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
    border1_options = [(c[0], c[1]) for c in border1_qs
        .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
    return border1_options


class CustomerListFilterForm(forms.ModelForm):
    """ A search/filter form for customers, primarily for the customer list view."""

    # We use a CharField here, as we want to allow entering
    # partial or invalid numbers. We name this phone instead of phones
    # to avoid the default model phonenumber field validation.
    phone = forms.CharField(
        required=False,
        label=_("Phone Number Contains..."),
    )

    # ModelForm cannot search for id (pk), so to add this capability we
    # create a separate search field, and wire it together in the form validation.
    customer_id = forms.IntegerField()

    # Border0 (e.g. Country) is a ForeignKey relationship but we want a multiple choice selector
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
    # Border1 (e.g. County) is a ForeignKey relationship but we want a multiple choice selector
    border1 = forms.MultipleChoiceField(
        required=False,
        label=_("County/Region"),
        choices=_get_border1s,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by County/Region',
            },
        )
    )
    created_from = forms.DateTimeField(
        label=_('Joined from date'),
        widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD hh:mm'}),
    )
    created_to = forms.DateTimeField(
        label=_('Joined to date'),
        widget=forms.DateTimeInput(attrs={'placeholder': 'YYYY-MM-DD hh:mm'})
    )
    complete_location = forms.ChoiceField(
        required=False,
        choices=(("ALL", BLANK_CHOICE_DASH),
                 ("Yes", _("Only customers with complete location details")),
                 ("No", _("Only customers without complete location details"))),
        initial='ALL',
        label=_("Has complete location details"),
        # help_text=_("<small>Complete location means the customer record has all location details set.</small>")
    )
    has_gender = forms.ChoiceField(
        required=False,
        choices=(("ALL", BLANK_CHOICE_DASH),
                 ("Yes", _("Only customers with gender recorded")),
                 ("No", _("Only customers without gender recorded"))),
        initial='ALL',
        label=_("Has gender details"),
    )
    sex = forms.ChoiceField(
        required=False,
        choices=list(BLANK_CHOICE_DASH) + list(SEX.choices),
        label=_("Gender"),
    )
    last_editor = forms.MultipleChoiceField(
        required=False,
        choices=_get_users,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by Last Editor',
            },
        )
    )
    categories = forms.MultipleChoiceField(
        required=False,
        choices=_get_categories,
        widget=s2forms.Select2MultipleWidget(
            attrs={
                'placeholder': 'Click here to filter by Category',
            },
        )
    )

    class Meta:
        model = Customer
        # Don't do model validation on border0 or border1
        fields = ['customer_id', 'name', 'sex', 'categories',
                  'last_editor', 'join_method', 'stop_method', ]

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_id = "filter-form"
        self.helper.layout = Layout(
            Div(
                Div('customer_id',
                    'name',
                    'phone',
                    Div(
                        Div('has_gender', css_class='col-sm-6'),
                        Div('sex', css_class='col-sm-6'),
                        css_class="row"
                    ),
                    Div(
                        Div('join_method', css_class='col-sm-6'),
                        Div('stop_method', css_class='col-sm-6'),
                        css_class="row"
                    ),
                    'categories',
                    css_class="col-sm-6 border-right"),
                Div(
                    'complete_location',
                    Div(
                        Div('border0', css_class='col-sm-6'),
                        Div('border1', css_class='col-sm-6'),
                        css_class="row"
                    ),
                    HTML("""<hr>"""),
                    Div(
                        Div('created_from', css_class='col-sm-6'),
                        Div('created_to', css_class='col-sm-6'),
                        css_class="row"
                    ),
                    'last_editor',
                    FormActions(
                        Submit('filter', 'Filter'),
                        StrictButton('Reset',
                                     id='reset-filter-form',
                                     css_class='btn-secondary'),
                        css_class="mt-auto ml-auto"
                    ),
                    css_class="col-sm-6  d-flex flex-column"
                ),
                css_class="row"
            ),
        )

        super().__init__(*args, **kwargs)

        # Refresh the choices since django-select2 does not allow choices or queryset
        # to be a runtime callable and the options may have changed since system start.
        self.fields['border1'].choices = _get_border1s

        # it's a search form, so we don't require anything
        for fieldname in self.fields:
            self.fields[fieldname].required = False


class CropHistoryItemForm(forms.ModelForm):

    class Meta:
        model = CropHistory
        fields = ('customer', 'commodity', 'date_planted', 'used_certified_seed',
                  'acres_planted', 'cost_of_seeds', 'cost_of_fertilizer', 'cost_currency',
                  'harvest_amount', 'harvest_units')
        field_classes = {
            'commodity': agri_forms.CommodityChoiceField,
        }
        widgets = {
            'customer': forms.HiddenInput(),
            'date_planted': forms.DateInput(attrs={'placeholder': 'DD/MM/YYYY'}),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'customer',
            Div(
                Div('date_planted', css_class='col-md-3'),
                Div('commodity', css_class='col-md-3'),
                Div('acres_planted', css_class='col-md-3'),
                Div('used_certified_seed', css_class='col-md-3'),
                css_class='row'
            ),
            Div(
                Div('cost_of_seeds', css_class='col-md-3'),
                Div('cost_of_fertilizer', css_class='col-md-3'),
                Div('cost_currency', css_class='col-md-3'),
                css_class='row'
            ),
            Div(
                Div('harvest_amount', css_class='col-md-3'),
                Div('harvest_units', css_class='col-md-3'),
                css_class='row'
            ),
            HTML("<hr>"),
            FormActions(
                Submit('submit', 'Save', css_class='btn btn-primary'),
                HTML("""<a role="button" class="btn btn-primary"
                        href="{% url 'customers:customer_crop_history_list' customer.id %}">Cancel</a>""")
            )
        )
        super().__init__(*args, **kwargs)
        self.fields['commodity'].queryset = Commodity.objects.all()


class AddCommodityForm(forms.Form):
    commodity = forms.ModelChoiceField(
        required=True,
        queryset=Commodity.objects.none(),  # Set in __init__
        widget=AuthModelSelect2Widget(
            model=Commodity,
            queryset=Commodity.objects.none(),  # Set in __init__
            search_fields=['name__icontains'],
            max_results=300,
            attrs={'data-minimum-input-length': 0},
        ),
    )
    customer = forms.Field(widget=forms.HiddenInput(), required=True)
    subscription_flag = forms.ChoiceField(choices=SUBSCRIPTION_FLAG.choices, required=False)

    class Meta:
        fields = ('customer', 'commodity', 'subscription_flag')

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'customer',
            'commodity',
            'subscription_flag',
            FormActions(
                Submit('submit', 'Add', css_class='btn btn-primary btn-sm')
            )
        )
        if 'instance' in kwargs:
            self.customer = kwargs.pop('instance')
        super().__init__(*args, **kwargs)
        self.fields['commodity'].queryset = Commodity.objects.order_by(Lower('name'))
        self.fields['commodity'].widget.queryset = Commodity.objects.order_by(Lower('name'))


class MarketSubscriptionForm(forms.ModelForm):

    class Meta:
        model = MarketSubscription
        fields = ('customer', 'market', 'backup', 'commodity')
        widgets = {
            'customer': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'customer',
            'market',
            'backup',
            'commodity',
            FormActions(
                Submit('submit', 'Save', css_class='btn btn-primary')
            )
        )
        super().__init__(*args, **kwargs)
        self.fields['market'].queryset = Market.objects.all()
        self.fields['backup'].queryset = Market.objects.filter(is_main_market=True)


class TipSeriesSubscriptionForm(forms.ModelForm):

    class Meta:
        model = CustomerCommodity
        fields = ('customer', 'commodity', 'subscription_flag')
        field_classes = {
            'commodity': tip_forms.TipSeriesChoiceField,
        }
        widgets = {
            'customer': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'commodity', 'subscription_flag', 'customer',
            FormActions(
                Submit('submit', 'Save', css_class='btn btn-primary')
            )
        )
        super().__init__(*args, **kwargs)

