from datetime import timedelta, datetime
from typing import Any, Optional
from callcenters.models import CallCenter
import humanize

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from agri.models import Commodity
from core.models import TimestampedBase
from core.constants import LANGUAGES
from customers.models import Customer

import sentry_sdk

from search.indexes import ESIndexableMixin
from sms.models import OutgoingSMS


class Tip(ESIndexableMixin, TimestampedBase):
    INDEX_FIELDS = ['id', 'commodity', 'translations', 'call_center']
    INDEX_ON_SAVE = False

    # NOTE(apryde): There don't seem to be any tips with border1 set and legay=False).
    border1 = models.ForeignKey(
        "world.Border", blank=True, null=True, on_delete=models.PROTECT
    )
    delay = models.DurationField(
        help_text=_("The time after the series starts that this tip is sent")
    )
    commodity = models.ForeignKey(
        Commodity, related_name='tips',
        on_delete=models.CASCADE
    )
    legacy: bool = models.BooleanField(default=False)

    call_center = models.ForeignKey(
        CallCenter, related_name='tips', on_delete=models.CASCADE
    )

    @property
    def delay_days(self) -> int:
        return self.delay.days

    class Meta:
        ordering = ['delay']

    def __str__(self):
        params = {
            'n': self.commodity.name,
            'pk': self.pk,
            'start': self.commodity.epoch_description,
        }
        if self.delay == timedelta():
            format_str = "{n} (#{pk}): send at the start"
        else:
            params['d'] = humanize.naturaldelta(self.delay)
            if self.delay > timedelta():
                format_str = "{n} (#{pk}): send {d} before {start}"
            else:
                format_str = "{n} (#{pk}): send {d} after {start}"
        return format_str.format(**params)

    @classmethod
    def mapping(cls):
        mapping_config = super().mapping()
        mapping_config['properties']['delay_days'] = {'type': 'integer'}
        return mapping_config

    def should_index(self) -> bool:
        return not self.legacy

    def to_dict(self) -> dict[str, Any]:
        fk_fields = ['commodity', 'call_center']
        nested_fields = ['translations']
        serialized = dict([(field_name, getattr(self, field_name)) for field_name in self.INDEX_FIELDS if field_name not in fk_fields + nested_fields])
        for fk_field in fk_fields:
            serialized[f"{fk_field}_id"] = getattr(self, f"{fk_field}_id")
        serialized['translations'] = [translation.to_dict() for translation in self.translations.all()]
        serialized['delay_days'] = self.delay_days
        return serialized


class TipTranslation(ESIndexableMixin, TimestampedBase):
    INDEX_FIELDS = ['language', 'text', 'tip', 'id']
    INDEX_ON_SAVE = False
    NESTED = True
    language = models.CharField(
        _("language"),
        max_length=3,  # ISO 639-3 code
        choices=LANGUAGES.choices,
        default=LANGUAGES.ENGLISH,
    )
    text = models.TextField(
        verbose_name=_("Tip content")
    )
    tip: Tip = models.ForeignKey(
        'tips.Tip',
        blank=False,
        null=False,
        on_delete=models.CASCADE,
        related_name='translations',
    )

    def validate_unique(self, exclude=None):
        """
        Validate the uniqueness at the db level. This should never fail.
        """
        super().validate_unique(exclude)
        # Ensure self is the only response in this tip with this language
        count = TipTranslation.objects.filter(
            tip=self.tip, language=self.language
        ).count()
        if count > 1:
            # Raise a sentry_sdk issue rather than a ValidationError, because
            # the later could make the user get stuck without the ability to fix it.
            sentry_sdk.capture_message(f"TipTranslation({self.pk}: Only one response for "
                                       f"each language is allowed but {count} found")
            # raise ValidationError(
            #     message="Only one translation for each language is allowed.",
            #     code="unique_together",
            # )
    def should_index(self) -> bool:
        return not self.tip.legacy

    def to_dict(self, **kwargs) -> dict[str, Any]:
        return {
            'id': self.pk,
            'language': self.language,
            'text': self.text,
            'tip_id': self.tip_id
        }


class TipSeries(TimestampedBase):
    """
    NOTE(apryde): This seems to now be redundant
    """
    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
    )
    commodity = models.ForeignKey(
        "agri.Commodity",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="tip_series",
    )
    start_event = models.CharField(
        max_length=255,
        blank=True,
        help_text=_(
            "The event which tips are sent in relation to, e.g.,"
            "calf due date or start of the year"
        ),
    )
    end_message = models.TextField(
        blank=True,
        default="",
        help_text=_("Message sent to customer when tip series finishes"),
    )
    legacy: bool = models.BooleanField()

    class Meta:
        verbose_name_plural = _("Tip Series")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'commodity_id': self.commodity_id,
        }


class TipSeriesSubscription(TimestampedBase):
    """
    NOTE(apryde): This appears to have been made obsolete by
    https://github.com/the-mediae-co/ishamba/pull/866.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='tip_subscriptions')
    series = models.ForeignKey(TipSeries, verbose_name=_('Tip series'), on_delete=models.CASCADE, related_name='subscriptions')
    start = models.DateTimeField(help_text=_('The date to start this subscription'))
    ended = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        try:
            return "{} <--> {}".format(self.customer, self.series.name)
        except Customer.DoesNotExist:
            # django-import-export runs force_str(instance) on
            # instances before they have been created and raises
            # an Exception as self.customer isn't populated.
            return ''

    def clean(self):
        # Restrict the number of active subscriptions
        max_allowed = self.customer.subscriptions.get_usage_allowance('tips')
        active_subscriptions = self.customer.tip_subscriptions.filter(ended=False).count()

        # Print for debugging purposes
        print(f"Max allowed: {max_allowed}, Active subscriptions: {active_subscriptions}")

        if self.pk is None and active_subscriptions >= max_allowed:
            raise ValidationError(f"You can only set {max_allowed} tip series subscriptions for this customer")


class TipSent(TimestampedBase):
    """
    Tracks whether a tip has been sent under a given subscription, to avoid re-sending when restarting
    """
    tip = models.ForeignKey(Tip,
                            on_delete=models.CASCADE,
                            related_name='sent')
    subscription = models.ForeignKey(TipSeriesSubscription,
                                     on_delete=models.CASCADE,
                                     related_name='tips_sent')

    class Meta:
        unique_together = ('tip', 'subscription')
        ordering = ('-created',)


class BulkTipSeriesSubscription(TimestampedBase):
    """
    A db-only class primarily used by BulkTipSeriesSubscriptionAdmin for
    creating bulk TipSeriesSubscription for all customers in a category.
    """
    categories = models.ManyToManyField(
        "customers.CustomerCategory",
    )
    tip_series = models.ForeignKey(
        TipSeries,
        verbose_name=_("Tip series"),
        on_delete=models.CASCADE,
        related_name="bulk_subscriptions",
    )
    start = models.DateTimeField(
        help_text=_("The date to start these subscriptions")
    )

    class Meta:
        verbose_name = "Bulk TipSeries Subscription"
        verbose_name_plural = "Bulk TipSeries Subscriptions"


class TipSeason(ESIndexableMixin, TimestampedBase):
    INDEX_FIELDS = ['commodity', 'start_date', 'season_length_override']
    commodity = models.ForeignKey(
        Commodity, related_name='tip_seasons',
        on_delete=models.CASCADE
    )
    start_date = models.DateField()
    customer_filters = models.JSONField(null=True, blank=True)
    season_length_override = models.PositiveIntegerField(null=True, blank=True)

    @property
    def end_date(self) -> Optional[datetime]:
        if not self.commodity.season_length_days:
            return None
        return self.start_date + timedelta(days=self.commodity.season_length_days)

    @classmethod
    def mapping(cls):
        mapping_config = super().mapping()
        mapping_config['properties']['end_date'] = {'type': 'date'}
        mapping_config['properties']['customer_filters'] = {'type': 'object', 'properties': {'border3': {'type': 'integer'}}}
        return mapping_config

    def to_dict(self) -> dict[str, Any]:
        fk_fields = ['commodity']
        serialized = dict([(field_name, getattr(self, field_name)) for field_name in self.INDEX_FIELDS if field_name not in fk_fields])
        for fk_field in fk_fields:
            serialized[f"{fk_field}_id"] = getattr(self, f"{fk_field}_id")
        serialized['end_date'] = self.end_date
        serialized['customer_filters'] = self.customer_filters
        return serialized

    def should_index(self) -> bool:
        return True

    def __str__(self) -> str:
        return f"{self.commodity}: {self.start_date} - {self.end_date}"


class TipMessage(TimestampedBase):
    tip_translation: TipTranslation = models.ForeignKey(TipTranslation, related_name='tip_messages', on_delete=models.CASCADE)
    tip_season: TipSeason = models.ForeignKey(TipSeason, related_name='tip_messages', on_delete=models.CASCADE)
    message: OutgoingSMS = models.OneToOneField(OutgoingSMS, related_name='tip_message', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('tip_translation', 'tip_season')

    def __str__(self) -> str:
        return f"{self.tip_translation} {self.tip_season} {self.message}"
