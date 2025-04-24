from __future__ import annotations
from collections import defaultdict
from functools import cached_property
from typing import Any, Optional, Tuple, Union
import hashlib
from typing import Optional, Tuple, Union, TYPE_CHECKING

import sentry_sdk
from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.utils import timezone, formats
from django.utils.translation import gettext_lazy as _

import phonenumbers
from dateutil.relativedelta import relativedelta
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber
from agri.constants import SUBSCRIPTION_FLAG
from agri.models import Commodity
from callcenters.models import CallCenter
from core.constants import FARM_SIZES, LANGUAGES, MARITAL_STATUS, PHONE_TYPES, SEX
from customers.constants import JOIN_METHODS, STOP_METHODS, HEARD_ABOUT_US
from core.models import TimestampedBase
from search.indexes import ESIndexableMixin
from sms.constants import KENYA_COUNTRY_CODE, OUTGOING_SMS_TYPE, UGANDA_COUNTRY_CODE, ZAMBIA_COUNTRY_CODE
from world.models import Border, BorderLevelName
from world.utils import get_border_for_location, get_country_for_phone
from gateways import gateways

from .managers import CommoditySubscriptionManager, CustomerQuerySet

if TYPE_CHECKING:
    from subscriptions.models import Subscription


class Customer(ESIndexableMixin, TimestampedBase):
    INDEX_FIELDS = [
        'id', 'name', 'sex', 'dob', 'relationship_status', 'phone_number_hash',
        'digifarm_farmer_id', 'border0', 'border1', 'border2', 'border3',
        'agricultural_region', 'weather_area', 'village', 'postal_address', 'postal_code',
        'preferred_language', 'phone_type', 'join_method', 'stop_method', 'is_registered', 'has_requested_stop',
        'stop_date', 'farm_size', 'owns_farm'
    ]
    class Meta:
        permissions = [
            ("export", "Can export tasks"),
        ]
        indexes = [
            models.Index(fields=['phone_number_hash'], name='phone_number_hash_idx'),
        ]

    name = models.CharField(_('name'), max_length=120, blank=True)
    sex = models.CharField(
        _('sex'),
        max_length=8,
        choices=SEX.choices,
        blank=True
    )
    dob = models.DateField(
        verbose_name=_('Date of birth'),
        blank=True,
        null=True
    )
    relationship_status = models.CharField(
        verbose_name=_('Relationship status'),
        max_length=255,
        choices=MARITAL_STATUS.choices,
        blank=True,
    )
    id_number = models.CharField(
        verbose_name=_('National ID number'),
        max_length=255,
        blank=True,
    )
    has_bank = models.BooleanField(
        verbose_name=_('Member of a bank'),
        help_text=_('Does the farmer have an account with a bank'),
        blank=True,
        null=True,
    )
    bank = models.ForeignKey(
        'customers.CustomerBank',
        verbose_name=_('Bank'),
        help_text=_("Name of the farmer's bank"),
        blank=True,
        null=True,
        related_name="customers",
        on_delete=models.PROTECT
    )
    has_savings_coop = models.BooleanField(
        verbose_name=_('Member of a savings cooperative'),
        help_text=_('Does the farmer have an account with a savings cooperative'),
        blank=True,
        null=True,
    )
    savings_coop = models.ForeignKey(
        'customers.CustomerSavingsCoop',
        verbose_name=_('Savings cooperative'),
        help_text=_("Name of the farmer's savings cooperative"),
        blank=True,
        null=True,
        related_name="customers",
        on_delete=models.SET_NULL
    )
    has_cooperative = models.BooleanField(
        verbose_name=_('Member of a farming cooperative'),
        help_text=_('Does the farmer sell their produce through a cooperative'),
        blank=True,
        null=True,
    )
    cooperative = models.ForeignKey(
        'customers.CustomerCoop',
        verbose_name=_('Cooperative'),
        help_text=_("Name of the farmer's farming cooperative"),
        blank=True,
        null=True,
        related_name="customers",
        on_delete=models.SET_NULL
    )
    has_farmer_group = models.BooleanField(
        verbose_name=_('Member of a farmer group'),
        help_text=_('Does the farmer belong to a group of farmers'),
        blank=True,
        null=True,
    )
    farmer_group = models.CharField(
        verbose_name=_('Farmer group'),
        max_length=255,
        blank=True,
    )

    # The CustomerPhone table (via foreign key set up on CustomerPhone class) contains phone numbers
    # that belong to this user. The referring field on this class is named 'phones'.

    # The digifarm customer mapping ID. It is not possible to determine a valid phone
    # number from this field, but its presence indicates that this is a Digifarm customer.
    digifarm_farmer_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    # location fields
    location = gis_models.PointField(geography=True, null=True, blank=True)
    # Country
    border0 = models.ForeignKey(
        'world.Border',
        null=True,
        blank=True,
        related_name="border0_of",
        on_delete=models.SET_NULL,
        limit_choices_to={'level': 0},
    )
    # County / Region / State
    border1 = models.ForeignKey(
        'world.Border',
        null=True,
        blank=True,
        related_name="border1_of",
        on_delete=models.SET_NULL,
        limit_choices_to={'level': 1},
    )
    # Subcounty / District / County
    border2 = models.ForeignKey(
        'world.Border',
        null=True,
        blank=True,
        related_name="border2_of",
        on_delete=models.SET_NULL,
        limit_choices_to={'level': 2},
    )
    # Ward / Township
    border3 = models.ForeignKey(
        'world.Border',
        null=True,
        blank=True,
        related_name="border3_of",
        on_delete=models.SET_NULL,
        limit_choices_to={'level': 3},
    )

    village = models.CharField(_('village'), max_length=120, blank=True)

    postal_address = models.TextField(_('Postal address'), blank=True)
    postal_code = models.CharField(_('Postal code'), blank=True, max_length=255)

    agricultural_region = models.ForeignKey(
        'agri.Region',
        verbose_name=_('agricultural region'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    weather_area = models.ForeignKey(
        'weather.WeatherArea',
        null=True,
        editable=False,
        verbose_name=_('weather area'),
        on_delete=models.SET_NULL
    )
    commodities = models.ManyToManyField(
        'agri.Commodity',
        through='CustomerCommodity',
        related_name='customers',
        verbose_name=_('commodities farmed'),
        blank=True
    )

    # info fields
    preferred_language = models.CharField(
        _('preferred language'),
        max_length=3,  # ISO 639-3 code
        choices=LANGUAGES.choices,
        default=LANGUAGES.ENGLISH,
    )
    phone_type = models.CharField(
        _('phone type'),
        max_length=50,
        choices=PHONE_TYPES.choices,
        blank=True
    )
    heard_about_us = models.CharField(
        _('how the customer heard about us'),
        max_length=50,
        choices=HEARD_ABOUT_US.choices,
        blank=True
    )
    farm_size = models.CharField(
        _('size of farm (acres)'),
        max_length=50,
        choices=FARM_SIZES.choices,
        blank=True,
        null=True
    )
    owns_farm = models.BooleanField(_('owns farm'), blank=True, null=True)
    notes = models.TextField(
        _('notes'),
        blank=True,
        help_text=_("Permanent notes about this customer not related to a "
                    "one-off issue.")
    )

    categories = models.ManyToManyField(
        'customers.CustomerCategory',
        blank=True
    )

    is_registered = models.BooleanField(_('is registered'), default=False)
    _original_is_registered = None  # for detecting changes

    date_registered = models.DateField(blank=True, null=True)
    join_method = models.CharField(
        verbose_name=_('how this customer joined'),
        max_length=20,
        choices=JOIN_METHODS.choices,
        default=JOIN_METHODS.UNKNOWN,
        blank=True,
    )

    has_requested_stop = models.BooleanField(
        _('has requested stop'),
        default=False
    )
    stop_method = models.CharField(
        verbose_name=_('how this customer stopped'),
        max_length=20,
        choices=STOP_METHODS.choices,
        default=STOP_METHODS.UNKNOWN,
        blank=True,
    )
    stop_date = models.DateField(
        verbose_name=_('when this customer requested stop'),
        blank=True,
        null=True,
    )

    markets = models.ManyToManyField(
        'markets.Market',
        through='markets.MarketSubscription',
        through_fields=['customer', 'market']
    )
    phone_number_hash = models.CharField(max_length=256, null=True, blank=True)  # caches main phonenumber gdpr hash

    skip_ai_invocation = models.BooleanField(
        _('do not invoke ai for this customer'),
        default=False,
    )

    # Override the default manager with a GeoManager instance.
    objects = CustomerQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_is_registered = self.is_registered

    def __str__(self):
        return "{}:{}".format(self.pk, self.name)

    def get_preferred_language(self) -> str:
        return self.get_preferred_language_display()

    def save(self, *args, **kwargs):
        """
        Automatically populates date_registered when required.
        """
        # If we're changing the value of is_registered to 'True', and it is the
        # first time registering, i.e. date_registered is blank, store the date
        # now
        if self.is_registered and not self._original_is_registered and not self.date_registered:
            self.date_registered = timezone.now().date()

        # Try our best to ensure that a country is set for all customers
        if not self.border0:
            if any([self.border1, self.border2, self.border3]):
                # Set the customer's other administrative boundaries based on what we have
                if self.border3 and not self.border2:
                    self.border2 = self.border3.parent
                if self.border2 and not self.border1:
                    self.border1 = self.border2.parent
                if self.border1 and not self.border0:
                    self.border0 = self.border1.parent
            elif self.id and self.main_phone:
                # If we've been created in the DB, and have a main_phone,
                # guess the customer's country (border0) by their phone number
                try:
                    country = get_country_for_phone(self.main_phone)
                    self.border0 = country
                except ValueError:
                    pass

        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.location and self.border1:
            # if not is_valid_border_for_location(self.border1, self.location):
            if not self.border1.border.contains(self.location):
                border_name = BorderLevelName.objects.get(country=self.border0, level=1).name
                sentry_sdk.capture_message(f'Customer {self.id} {border_name} and location do not correspond')
                # We used to raise validation error here. However, this is tricky. Changing the cutoff
                # distance or the border geometry dataset could render a previously valid customer
                # invalid, and prevent it from being saved when making changes unrelated to the customer
                # location. Perhaps there is a need to prevent making such change through UI, but we
                # should not completely disable a customer just because two fields and inconsistent.
                # raise ValidationError("The customer's location and border do not "
                #                       "correspond with each other")
        elif self.location:
            self.border1 = get_border_for_location(self.location, 1)

        if self.bank and self.has_bank is not True:
            raise ValidationError({'has_bank': _("Bank name supplied but customer is not marked as having a bank")})

        if self.cooperative and self.has_cooperative is not True:
            raise ValidationError(
                {'has_cooperative': _("Cooperative name supplied but customer is not marked as having a cooperative")})

        if self.savings_coop and self.has_savings_coop is not True:
            raise ValidationError({'has_savings_coop': _(
                "Savings cooperative name supplied but customer is not marked as having a savings cooperative")})

        if self.farmer_group and self.has_farmer_group is not True:
            raise ValidationError({'has_farmer_group': _(
                "Farmer group name supplied but customer is not marked as having a farmer group")})

    def clean_fields(self, exclude=None):
        """
        Validation for .phones
        """
        from sms import utils as sms_utils

        super().clean_fields(exclude)
        errors = defaultdict(list)

        # Don't validate phones if we aren't a record in the DB yet.
        if not self.id:
            return

        if 'phones' not in exclude:
            try:
                for phone in self.phones.all():
                    # This form is used to enter new customers, so allow international numbers here.
                    phone and sms_utils.validate_number(phone, allow_international=True)
            except ValidationError as e:
                errors['phones'].append(e.message)

            if errors:
                raise ValidationError(errors)

    @property
    def call_center(self) -> Optional[CallCenter]:
        if call_center := getattr(self.border3, 'call_center', None):
            return call_center
        if call_center := getattr(self.border2, 'call_center', None):
            return call_center
        if call_center := getattr(self.border1, 'call_center', None):
            return call_center
        if call_center := getattr(self.border0, 'call_center', None):
            return call_center
        return None

    @property
    def main_phone(self):
        """
        Return the customer's "main" phonenumber object. This works both with multiple
        numbers as well as with the digifarm fake numbers, returning the customer's
        main (and real) phone number. If only a fake DF number exists, we return None.
        """
        if not self.phones.exists():
            return None

        # Check if an 'is_main' number exists in the CustomerPhone table for this customer.
        # If so, check that it's not a fake digifarm number, and then return it.
        try:
            main = self.phones.get(is_main=True).number
            if main.country_code != phonenumbers.country_code_for_region('DE'):
                return main
        except CustomerPhone.DoesNotExist:
            return None
        except CustomerPhone.MultipleObjectsReturned:
            sentry_sdk.capture_message(f"Multiple is_main phone numbers for customer {self.id}")
            # Pick one at random
            main = self.phones.filter(is_main=True).exclude(
                number__startswith='+' + str(phonenumbers.country_code_for_region('DE'))
            ).order_by('?').first().number
            return main

        # Otherwise, no valid number is known (should never get here)
        return None

    def format_phone_number(self, number_format='INTERNATIONAL'):
        """
        Kwargs:
            number_format (string):
                - 'INTERNATIONAL' (e.g. +254 711 498906)
                - 'NATIONAL'      (e.g. 0711 498906)
                - 'E164'          (e.g. +254711498906)
        """
        phone_number_format = getattr(phonenumbers.PhoneNumberFormat, number_format)
        return phonenumbers.format_number(self.main_phone, phone_number_format) if self.main_phone else '—'

    @property
    def formatted_phone(self):
        return self.format_phone_number()

    def extend_subscription(self, duration_delta, payment=None):
        """
        Requires a timedelta argument, and an optional payment object kwarg.
        Returns a newly-created Subscription object (the name
        'extend_subscription' is therefore a bit misleading, but makes sense
        for the way it's used).

        If the customer has an existing active or upcoming subscription, the
        newly-created subscription will start the day after their latest
        subscription ends. Otherwise it will start from today.

        Note: the use of an extra relativedelta(days=-1) to avoid off-by-one
        errors.
        """
        from subscriptions.models import Subscription
        today = timezone.now().date()
        try:
            existing = (Subscription.objects.potent()
                        .filter(customer=self, end_date__gte=today)
                        .latest('end_date'))
        except Subscription.DoesNotExist:
            start_date = today
        else:
            start_date = existing.end_date + relativedelta(days=1)

        return Subscription.objects.create(
            customer=self,
            start_date=start_date,
            end_date=start_date + duration_delta + relativedelta(days=-1)
        )

    @property
    def currently_subscribed(self):
        return self.subscriptions.active().exists()

    @property
    def current_subscription(self) -> Optional[Subscription]:
        from subscriptions.models import Subscription
        today = timezone.now().date()
        try:
            premium_existing = (Subscription.objects.potent()
                            .filter(customer=self, end_date__gte=today)
                            .filter(type__is_premium=True)
                            .order_by('end_date').last())
            if premium_existing:
                return premium_existing
            freemium_existing = (Subscription.objects.potent()
                            .filter(customer=self, end_date__gte=today)
                            .filter(type__is_premium=False)
                            .order_by('end_date').last())
            if freemium_existing:
                return freemium_existing
        except Subscription.DoesNotExist:
            return None

    @property
    def is_lapsed(self):
        today = timezone.now().date()
        return (not self.subscriptions.not_permanent().active()
                and self.subscriptions.filter(end_date__lt=today).exists())

    @property
    def never_subscribed(self):
        return not self.subscriptions.exists()

    @property
    def should_receive_messages(self):
        """
        High-level composite property. Use this everywhere else in code, so
        that logic changes can be made in one place.
        """
        # Use queryset method to avoid keeping business logic sync'd
        return self.pk and (Customer.objects.should_receive_messages()
                            .filter(pk=self.pk)
                            .exists())

    @property
    def can_access_call_centre(self):
        # Use queryset method to avoid keeping business logic sync'd
        return self.pk and (Customer.objects.can_access_call_centre()
                            .filter(pk=self.pk)
                            .exists())

    @property
    def tips_commodities(self) -> list[int]:
        if sub := self.current_subscription:
            if sub.is_premium:
                return list(
                    self.customer_commodities.filter(
                        subscription_flag=SUBSCRIPTION_FLAG.PREMIUM
                    ).values_list('commodity_id', flat=True).distinct()
                )
        return list(
            self.customer_commodities.filter(
                subscription_flag=SUBSCRIPTION_FLAG.FREEMIUM
            ).order_by('-created').values_list('commodity_id', flat=True)[:1]
        )

    def can_add_tipsubscription(self):
        allowance = self.subscriptions.get_usage_allowance('tips')
        usage = self.tip_subscriptions.exclude(ended=True).count()
        return usage <= allowance

    def can_add_marketsubscription(self):
        allowance = self.subscriptions.get_usage_allowance('markets')
        return self.market_subscriptions.count() <= allowance

    def enroll(self, join_sms=None, **kwargs):
        """
        For not-already-active customers, send an appropriate response. For
        existing customers who are re-joining, change their 'has_requested_stop',
        'stop_method' and 'stop_date' values and send an SMS response.

        join_sms: The IncomingSMS message that triggered this enrollment.

        If this action is triggered by a JOIN sms then the source of the Task
        created will be the incoming sms. If it's by the api, the source will be
        the customer itself.

        kwargs may contain the key 'using_numbers' which specifies the phone
        number to send any response to. This should only apply to existing
        customers who are re-joining.
        """
        from sms.models import OutgoingSMS
        from sms.tasks import send_message
        from sms import utils as sms_utils

        # Determine what kind of customer is being enrolled
        if join_sms is None or join_sms.customer_created:  # If newly created customer
            key = settings.SMS_JOIN
        elif self.has_requested_stop:  # previously active but requested stop
            key = settings.SMS_INACTIVE_CUSTOMER_REJOIN
            self.has_requested_stop = False
            self.stop_method = ''
            self.stop_date = None
            self.save(update_fields=['has_requested_stop', 'stop_method', 'stop_date'])
        else:  # current and active customer
            key = settings.SMS_ACTIVE_CUSTOMER_JOIN

        message, sender, create_task = sms_utils.get_populated_sms_templates_text_and_task(key, customer=self)
        if join_sms:
            join_sms.create_and_send_sms_response(message, sender, **kwargs)
        else:
            sms = OutgoingSMS.objects.create(text=message,
                                             message_type=OUTGOING_SMS_TYPE.NEW_CUSTOMER_RESPONSE)
            send_message.delay(sms.id, [self.id], sender=sender, **kwargs)

        task = None
        if create_task:
            task = self.tasks.create(
                customer=self,
                description=f'{key} message',
                source=join_sms or self
            )
            if join_sms:
                task.incoming_messages.add(join_sms)

        return task

    def get_sms_text(self, template_name: str, skip_formatting: bool = False) -> tuple[str, str]:
        from sms import utils
        return utils.get_populated_sms_templates_text(template_name, self, skip_formatting=skip_formatting)

    def send_welcome_sms(self):
        from sms.models import OutgoingSMS
        from sms.tasks import send_message
        if self.preferred_language == LANGUAGES.ENGLISH:
            msg_key = settings.SMS_REGISTRATION_COMPLETED_ENGLISH
        else:
            msg_key = settings.SMS_REGISTRATION_COMPLETED_SWAHILI
        message_text, sender = self.get_sms_text(msg_key)
        sms_msg = OutgoingSMS.objects.create(text=message_text,
                                             message_type=OUTGOING_SMS_TYPE.NEW_CUSTOMER_RESPONSE)
        send_message.delay(sms_msg.id, [self.id], sender=sender, paginate=False)

    def get_or_create_misc_data(self):
        try:
            return self.misc_data
        except CustomerMiscData.DoesNotExist:
            return CustomerMiscData.objects.create(customer=self)

    def get_or_create_letitrain_data(self):
        try:
            return self.letitrain_data.get(season=get_current_farming_season())
        except CustomerLetItRainData.DoesNotExist:
            return CustomerLetItRainData.objects.create(customer=self, season=get_current_farming_season())

    @cached_property
    def subs_count(self) -> int:
        return self.subscriptions.count()

    @cached_property
    def sms_count(self) -> int:
        return self.incomingsms_set.count()

    @cached_property
    def calls_count(self) -> int:
        return self.call_set.count()

    @cached_property
    def crop_histories_count(self) -> int:
        return self.crophistory_set.count()

    @cached_property
    def commodity_names(self) -> str:
        return "/ ".join(self.commodities.values_list('name', flat=True))

    @cached_property
    def gps_coordinates(self) -> str:
        if self.location:
            return self.location.coords
        return ""

    @cached_property
    def gateway(self) -> Optional[int]:
        if self.digifarm_farmer_id:
            return gateways.DF
        elif self.main_phone:
            return gateways.AT
        return None

    def should_index(self) -> bool:
        return True

    @classmethod
    def mapping(cls):
        mapping_config = super().mapping()
        mapping_config['properties']['tips_commodities'] = {'type': 'integer'}
        mapping_config['properties']['commodities'] = {'type': 'integer'}
        mapping_config['properties']['categories'] = {'type': 'integer'}
        mapping_config['properties']['formatted_phone'] = {'type': 'keyword'}
        mapping_config['properties']['subscription_type'] = {'type': 'keyword'}
        mapping_config['properties']['current_subscription'] = {'type': 'integer'}
        mapping_config['properties']['call_center'] = {'type': 'integer'}
        return mapping_config

    def to_dict(self) -> dict[str, Any]:
        current_subscription = self.current_subscription
        fk_fields = ['border0', 'border1', 'border2', 'border3', 'agricultural_region', 'weather_area']
        serialized = {
            'formatted_phone': self.formatted_phone.replace(" ", ""),
            'subscription_type': current_subscription.type_id if current_subscription else None,
            'tips_commodities': self.tips_commodities,
            'commodities': list(self.commodities.values_list('id', flat=True)),
            'categories': list(self.categories.values_list('id', flat=True)),
            'call_center': self.call_center.id if self.call_center else None,
            **dict([(field_name, getattr(self, field_name)) for field_name in self.INDEX_FIELDS if field_name not in fk_fields])
        }
        for border_field in fk_fields:
            serialized[f"{border_field}_id"] = getattr(self, f"{border_field}_id")
        return serialized


class CustomerPhone(models.Model):
    """
    A class to encapsulate a DB table of phone numbers. Since a customer can have multiple phone numbers,
    the CustomerPhone has a many-to-one relationship with a customer. However, only one number is
    considered the 'main' number for a customer. This is used when e.g. sending a bulk sms.
    """
    number = PhoneNumberField(unique=True, null=False, blank=False)
    is_main = models.BooleanField(null=False, blank=False, default=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="phones")
    gdpr_hash = models.CharField(max_length=256, null=True, blank=True)

    class Meta:
        verbose_name = "Customer phone number"
        verbose_name_plural = "Customer phone numbers"
        # Enforce that there is only one main number per customer
        constraints = [
            models.UniqueConstraint(fields=["customer"],
                                    condition=Q(is_main=True),
                                    name='unique_customer_main_number'),

        ]
        indexes = [
            models.Index(fields=['is_main'], name='customers_phone_is_main_idx'),
        ]

    def __str__(self):
        return str(self.number)

    def save(self, *args, **kwargs):
        """
        django-phonenumber-field>=4.0.0 no longer validates numbers before
        saving to the DB so we need to check here before creating this record.
        """
        if self.number is None or len(self.number) == 0 or not phonenumbers.is_valid_number(self.number):
            raise ValueError(f"Invalid phone number ({self.number}) for customer: {self.customer}")
        self.gdpr_hash = hashlib.sha256(bytes(str(self.number), encoding='utf-8')).hexdigest()
        if self.is_main:
            phones = self.customer.phones.filter(is_main=True)
            if self.pk:
                phones = phones.exclude(pk=self.pk)

            main_count = phones.count()
            if main_count >= 1:
                raise ValidationError(
                    {'is_main': _(f"Customers may have only one 'main' phone number. This one has {main_count}.")}
                )
        super().save(*args, **kwargs)
        if self.is_main and self.customer.phone_number_hash != self.gdpr_hash:
            self.customer.phone_number_hash = self.gdpr_hash
            self.customer.save()


class CustomerBank(TimestampedBase):
    name = models.CharField(_('name'), max_length=255, unique=True)

    class Meta:
        verbose_name_plural = "Customer banks"

    def __str__(self):
        return self.name


class CustomerCategory(TimestampedBase):
    name = models.CharField(_('name'), max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Customer categories"
        ordering = [Lower('name')]

    def __str__(self):
        return self.name


class CustomerCoop(TimestampedBase):
    name = models.CharField(_('Name'), max_length=255, unique=True)
    activity = models.CharField(_('Activity'), max_length=255, blank=True)
    town = models.CharField(_('Town'), max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "Customer farming cooperatives"

    def __str__(self):
        return self.name


class CustomerCommodity(TimestampedBase):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='customer_commodities'
    )
    commodity = models.ForeignKey(
        Commodity, on_delete=models.CASCADE,
        related_name='customer_commodities'
    )
    primary = models.BooleanField(default=False)
    subscription_flag = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=SUBSCRIPTION_FLAG.choices
    )

    def __str__(self) -> str:
        return f"{self.customer}: {self.commodity}"

    class Meta:
        unique_together = ('customer', 'commodity')


class CropHistory(TimestampedBase):
    HARVEST_UNIT_TYPES = [
        ('kgs', 'kgs'),
        ('items', 'items'),
        ('50kgbag', '50 kg bags'),
        ('90kgbag', '90 kg bags'),
        ('100kgbag', '100 kg bags'),
    ]
    CURRENCY_TYPES = [
        ('kes', 'Kenya shillings'),
        ('gbp', 'Pound sterling'),
        ('ugx', 'Uganda shillings'),
        ('usd', 'US dollars'),
        ('zmw', 'Zambian Kwacha'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    commodity = models.ForeignKey('agri.Commodity', on_delete=models.CASCADE)
    date_planted = models.DateField()
    used_certified_seed = models.BooleanField(null=True, blank=True)
    acres_planted = models.FloatField(null=True, blank=True)
    cost_of_seeds = models.FloatField(null=True, blank=True)
    cost_of_fertilizer = models.FloatField(null=True, blank=True)
    cost_currency = models.CharField(choices=CURRENCY_TYPES, max_length=16, null=True, blank=True)
    harvest_amount = models.FloatField(null=True, blank=True)
    harvest_units = models.CharField(choices=HARVEST_UNIT_TYPES, max_length=16, null=True, blank=True)

    class Meta:
        verbose_name = "Crop history"
        verbose_name_plural = "Crop histories"

    def __str__(self):
        return f"{self.commodity.name}:{formats.date_format(self.date_planted, use_l10n=True)}"


def _limit_subscription_commodity_choices():
    """
    Limit commodity choices to those which get market prices, or which do
    not get market prices but also have no variant types (i.e. no source of
    market prices exists).
    """
    commodity_model = apps.get_model("agri", "commodity")
    eligible_pks = (
        commodity_model.objects.annotate(num_variants=Count("variants"))
        .filter(
            Q(gets_market_prices=True)
            | (Q(gets_market_prices=False) & Q(num_variants=0))
        )
        .values_list("pk", flat=True)
    )
    return {"pk__in": eligible_pks}


class CustomerSavingsCoop(TimestampedBase):
    name = models.CharField(_('name'), max_length=255, unique=True)

    class Meta:
        verbose_name_plural = "Customer savings cooperatives"

    def __str__(self):
        return self.name


class CommoditySubscription(TimestampedBase):
    subscriber = models.ForeignKey('Customer', verbose_name=_('subscriber'), on_delete=models.CASCADE)
    commodity = models.ForeignKey(
        'agri.Commodity',
        limit_choices_to=_limit_subscription_commodity_choices,
        verbose_name=_('commodity'),
        on_delete=models.CASCADE
    )
    epoch_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Start date'),
        help_text=_("This commodity is event based, and requires a start date")
    )
    ended = models.BooleanField(
        default=False,
        help_text=_("In the case of a moveable-feast subscription, indicates "
                    "that the customer has come to the end of the agri-tip "
                    "stream, and is receiving tips from the fallback "
                    "commodity.")
    )
    send_market_prices = models.BooleanField(default=True)
    send_agri_tips = models.BooleanField(default=False)

    objects = CommoditySubscriptionManager()

    def __init__(self, *args, **kwarg):
        super().__init__(*args, **kwarg)
        sentry_sdk.capture_message(f"CommoditySubscription being instantiated.")
        raise DeprecationWarning(f"CommoditySubscription is deprecated. Use markets/MarketSubscription as a replacement.")

    @staticmethod
    def get_relative_tip_number(epoch_date, date=None):
        """
        Calculates the relative Agri-Tip number based on the epoch date and
        a given date.

        Kwargs:
            epoch_date: Date subscription started on
            date: Date for which to calculate the relative tip number (defaults
                to the current date).
        Returns:
            int. AgriTipSMS.number to send on the given date.
        """
        sentry_sdk.capture_message(f"CommoditySubscription.get_relative_tip_number being called.")
        raise DeprecationWarning(f"CommoditySubscription is deprecated. Use markets/MarketSubscription as a replacement.")

        if date is None:
            date = timezone.now().date()

        # We round here because validation doesn't enforce epoch_date being a
        # Thursday (which the algorithm requires)
        week_delta = int(round((date - epoch_date).days / 7))
        tipnumber = week_delta // settings.AGRI_TIPS_SENDING_PERIOD
        return tipnumber

    def __str__(self):
        if self.epoch_date:
            has_ended = " (ended)" if self.ended else ""
            return "{} subscription, {} {}{}".format(
                self.commodity,
                self.commodity.epoch_description,
                self.epoch_date,
                has_ended
            )
        else:
            return "{} subscription".format(self.commodity, )

    def clean(self, *args, **kwargs):
        # Only check usage limits if this is a new CommoditySubscription
        if not self.pk:
            # Find the customer's usage limits
            customer = self.subscriber

            # Only validate if this commodity is flagged `send_agri_tips`
            if self.send_agri_tips and not customer.can_add_commoditysubscription(only_agri_tips=True):
                msg = _("Only {} tip subscriptions are allowed")
                max_agri_tips = customer.subscriptions.get_usage_allowance('agri_tips')
                raise ValidationError(msg.format(max_agri_tips))

            # Only validate if this commodity is flagged `send_market_prices`
            if self.send_market_prices and not customer.can_add_commoditysubscription(only_prices=True):
                msg = _("Only {} market price subscriptions are allowed")
                max_prices = customer.subscriptions.get_usage_allowance('prices')
                raise ValidationError(msg.format(max_prices))

        if self.send_market_prices and not self.commodity.gets_market_prices:
            raise ValidationError(
                _("{} doesn't receive market prices but 'Send market "
                  "prices' was checked.").format(str(self.commodity)))

        if (self.send_agri_tips and self.commodity.agri_tip_source
            and not self.commodity.agri_tip_source.agritipsms_set.exists()):
            raise ValidationError(
                _("{} doesn't have any associated Agri-tips but 'Send agri "
                  "tips' was checked").format(str(self.commodity.agri_tip_source)))

        try:
            if self.commodity.is_event_based and not self.epoch_date:
                msg = _("Subscriptions for {} need a start date")
                raise ValidationError({
                    'epoch_date': msg.format(self.commodity.name),
                })

            if not self.commodity.is_event_based and self.epoch_date:
                msg = _("Subscriptions for {} don't take a start date")
                raise ValidationError({
                    'epoch_date': msg.format(self.commodity.name),
                })
        except AttributeError:
            # We are Missing a required field. This will be detected elsewhere.
            pass

        return super().clean(*args, **kwargs)

    class RequiresGraduationError(Exception):
        """
        Raise this when a CommoditySubscription is due to be marked as
        ended=True. E.g. if trying to get an AgriTipSMS object for a commodity
        subscription, but the requested week number is higher than the highest
        week number of any AgriTipSMS object with a foreign-key to the relevant
        commodity.
        """
        pass



class CustomerQuestion(TimestampedBase):
    text = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Question"
        ordering = ['order']

    def __str__(self):
        return self.text

    def get_choices(self):
        choices = list(self.choices.values_list('text', flat=True))
        if choices:
            return [('', '--------')] + list(zip(choices, choices))
        else:
            return None


class CustomerQuestionChoice(TimestampedBase):
    text = models.CharField(max_length=255)
    question = models.ForeignKey(CustomerQuestion, on_delete=models.CASCADE, related_name='choices')
    order = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Choice"
        ordering = ['order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_text = self.text

    def __str__(self):
        return self.text

    def save(self, *args, **kwargs):
        if self._old_text != self.text:
            # Update saved choice values
            (CustomerQuestionAnswer.objects.filter(question_id=self.question_id)
             .filter(text=self._old_text)
             .update(text=self.text))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Set existing answers using this choice to be empty
        (CustomerQuestionAnswer.objects.filter(question_id=self.question_id)
         .filter(text=self.text)
         .update(text=''))
        super().delete(*args, **kwargs)


class CustomerQuestionAnswer(TimestampedBase):
    text = models.CharField(max_length=255, verbose_name="Answer", blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(CustomerQuestion, on_delete=models.PROTECT, related_name='answers')

    class Meta:
        verbose_name = "Answer"
        ordering = ['question__order']
        unique_together = (('customer', 'question'),)

    def __str__(self):
        return self.question.text + self.text


def get_or_create_customer_by_phone(phone: Union[str, PhoneNumber], join_method: str) -> Tuple[Customer, bool]:
    """Fetches or creates new customer by phone number, returning tuple (customer, created)"""
    try:
        db_phone = CustomerPhone.objects.get(number=phone)
        customer = db_phone.customer
        return customer, False
    except CustomerPhone.DoesNotExist:
        try:
            # Guess the customer's country (border0) by their phone number
            border0 = get_country_for_phone(phone)
        except ValueError:
            border0 = None
        except phonenumbers.NumberParseException:
            if str(phone).startswith(f"+{KENYA_COUNTRY_CODE}"):
                border0 = Border.objects.filter(country='Kenya',
                                                level=0).first()  # Avoid a potential DoesNotExist exception
            elif str(phone).startswith(f"+{UGANDA_COUNTRY_CODE}"):
                border0 = Border.objects.filter(country='Uganda',
                                                level=0).first()  # Avoid a potential DoesNotExist exception
            elif str(phone).startswith(f"+{ZAMBIA_COUNTRY_CODE}"):
                border0 = Border.objects.filter(country='Zambia',
                                                level=0).first()  # Avoid a potential DoesNotExist exception
            else:
                border0 = None

        customer = Customer.objects.create(border0=border0, join_method=join_method)
        db_phone = CustomerPhone.objects.create(number=phone, is_main=True, customer=customer)
        return customer, True


class CustomerMiscData(TimestampedBase):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name='misc_data',
        primary_key=True
    )
    school_name_raw = models.CharField(max_length=100, blank=True)
    county_name_raw = models.CharField(max_length=20, blank=True)
    livestock_raw = models.CharField(max_length=100, blank=True)
    livestock_unmatched = models.IntegerField(null=True, blank=True)
    crops_raw = models.CharField(max_length=100, blank=True)
    crops_unmatched = models.IntegerField(null=True, blank=True)


def get_current_farming_season():
    return CustomerLetItRainData.Seasons.Y2022S2.value


class CustomerLetItRainData(TimestampedBase):
    class Seasons(models.TextChoices):
        Y2022S2 = '2022s2', _('2022-2nd season')
        Y2023S1 = '2023s1', _('2023-1st season')
        __empty__ = _('Unknown')

    class DataSources(models.TextChoices):
        USSD = 'ussd', _('USSD')
        WEB = 'web', _('Web')
        __empty__ = _('Unknown')

    class FertilizerTypes(models.TextChoices):
        ORGANIC = 'organic', _('Organic')
        SYNTHETIC = 'synthetic', _('Synthetic')
        BOTH = 'both', _('both')
        __empty__ = _('Unknown')

    class WeatherSources(models.TextChoices):
        ISHAMBA = 'ishamba', _('iShamba')
        SSU = 'ssu', _('Shamba Shape Up')
        OTHER = 'other', _('Other')
        __empty__ = _('Unknown')

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='letitrain_data',
    )
    season = models.CharField(
        _('season'),
        max_length=6,
        choices=Seasons.choices,
        default=get_current_farming_season,
        blank=False,
        null=False,
    )
    data_source = models.CharField(
        _('data source'),
        max_length=8,
        choices=DataSources.choices,
        default=DataSources.USSD,
        blank=False,
        null=False,
    )
    guesses = ArrayField(
        models.DateField(blank=False),
        blank=True,
        null=True,
    )
    crops_have_failed = models.BooleanField(
        verbose_name=_('has had crops fail'),
        blank=True,
        null=True,
    )
    has_crop_insurance = models.BooleanField(
        verbose_name=_('has crop insurance'),
        blank=True,
        null=True,
    )
    receives_weather_forecasts = models.BooleanField(
        verbose_name=_('receives weather forecasts'),
        blank=True,
        null=True,
    )
    weather_source = models.CharField(
        _('weather source'),
        max_length=20,
        choices=WeatherSources.choices,
        blank=True,
        null=False,
    )
    forcast_frequency_days = models.IntegerField(null=True, blank=True)
    uses_certified_seed = models.BooleanField(null=True, blank=True)
    fertilizer_type = models.CharField(
        _('fertilizer type'),
        max_length=12,
        choices=FertilizerTypes.choices,
        blank=True,
        null=False,
    )
    has_experienced_floods = models.BooleanField(null=True, blank=True)
    has_experienced_droughts = models.BooleanField(null=True, blank=True)
    has_experienced_pests = models.BooleanField(null=True, blank=True)
    has_experienced_diseases = models.BooleanField(null=True, blank=True)

    @property
    def current_season(self):
        return get_current_farming_season()

    @property
    def is_complete(self):
        complete = self.season != '' and \
                   self.guesses and len(self.guesses) >= 3 and \
                   self.crops_have_failed is not None and \
                   self.has_crop_insurance is not None and \
                   self.receives_weather_forecasts is not None and \
                   self.weather_source != '' and \
                   self.forcast_frequency_days > 0 and \
                   self.uses_certified_seed is not None and \
                   self.fertilizer_type != '' and \
                   self.has_experienced_floods is not None and \
                   self.has_experienced_droughts is not None and \
                   self.has_experienced_pests is not None and \
                   self.has_experienced_diseases is not None

        return complete


class CustomerSurvey(TimestampedBase):

    class DataSources(models.TextChoices):
        USSD = 'ussd', _('USSD')
        WEB = 'web', _('Web')
        __empty__ = _('Unknown')

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='survey_data',
    )
    survey_start = models.DateTimeField(
        auto_now=False,
        auto_now_add=True,
        blank=False,
        null=False,
    )
    survey_title = models.CharField(
        max_length=255,
        blank=False,
        null=False,
    )
    data_source = models.CharField(
        _('data source'),
        max_length=8,
        choices=DataSources.choices,
        default=DataSources.USSD,
        blank=False,
        null=False,
    )
    responses = models.JSONField(
        blank=False,
        null=False,
    )
    finished_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGES.choices,
        null=True,
        blank=True,
    )

    def is_finished(self):
        return self.finished_at is not None

    def __str__(self):
        return f"{self.pk}:{self.customer.id}->{self.survey_title}"


class NPSResponse(models.Model):
    """
    A class to encapsulate a DB table of Net Promoter Score (NPS) Responses. NPS Responses
    can be entered via the automated SMS NPS query system or by CCO's when surveying via phone.
    """
    score = models.IntegerField(null=False, blank=False)
    raw_input = models.CharField(max_length=120, null=False, blank=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="nps_responses")
    created = models.DateTimeField(blank=False, null=False, auto_now_add=True)
    creator_id = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "NPS Response"
        verbose_name_plural = "NPS Responses"
        indexes = [
            models.Index(fields=['score'], name='nps_response_score_idx'),
            models.Index(fields=['created'], name='nps_response_created_idx'),
        ]

    def __str__(self):
        return f"{self.pk}:{self.customer.name}-{self.customer.border0.name}={self.score}"

    def save(self, *args, **kwargs):
        """
        Captures the acting user, via 'user' keyword argument
        """
        user = kwargs.pop('user', None)
        if user and not self.creator_id:
            self.creator_id = user.id
        return super().save(*args, **kwargs)

    def is_promoter(self) -> bool:
        return self.score >= 9

    def is_passive(self) -> bool:
        return self.score in (7, 8)

    def is_detractor(self) -> bool:
        return self.score <= 6
