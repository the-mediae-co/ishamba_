from typing import Dict
import cachetools

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedBase
from agri.constants import COMMODITY_TYPES, CALENDAR_TYPE_EVENT_BASED, CALENDAR_TYPE_SEASONAL


class Region(TimestampedBase):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Commodity(TimestampedBase):
    CROP = COMMODITY_TYPES.CROP
    LIVESTOCK = COMMODITY_TYPES.LIVESTOCK
    name = models.CharField(_('Name'), max_length=100, unique=True)
    short_name = models.CharField(_('Short name'), max_length=14, unique=True)
    commodity_type = models.CharField(
        _('Commodity type'),
        max_length=10,
        choices=COMMODITY_TYPES.choices,
        default=COMMODITY_TYPES.CROP)
    epoch_description = models.CharField(
        _('Epoch description'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('The event from which other dates are measured, e.g. '
                    '"calf due-date". Leave blank for seasonal commodities.'))
    variant_of = models.ForeignKey(
        'Commodity',
        related_name='variants',
        blank=True,
        null=True,
        help_text=_('The commodity-stream from which the customer will be '
                    'sent SMS tips. Leave blank if this commodity has its own '
                    'agri-tip stream.'),
        on_delete=models.CASCADE
    )
    fallback_commodity = models.ForeignKey(
        'Commodity',
        blank=True,
        null=True,
        help_text=_('For event-based agri-tip streams only: the commodity '
                    'that will supply tips when this stream ends.'),
        on_delete=models.SET_NULL
    )
    gets_market_prices = models.BooleanField(
        _('Gets market prices'),
        default=False,
        help_text=_('Market prices are regularly received for this commodity.'))
    season_length_days = models.IntegerField(
        blank=True,
        null=True,
        default=None,
        help_text=_('The max length of a typical growing season. '
                    'Leave blank for livestock and perennials.'),
    )
    tips_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = _("Commodities")
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property
    def calendar_type(self):
        if self.epoch_description:
            return CALENDAR_TYPE_EVENT_BASED
        else:
            return CALENDAR_TYPE_SEASONAL

    @property
    def is_event_based(self):
        return self.calendar_type == CALENDAR_TYPE_EVENT_BASED

    @property
    def is_crop(self):
        return self.commodity_type == COMMODITY_TYPES.CROP

    @property
    def is_livestock(self):
        return self.commodity_type == COMMODITY_TYPES.LIVESTOCK

    @property
    def agri_tip_source(self):
        return self.variant_of or self

    @property
    def tips_count(self) -> int:
        return self.tips.filter(legacy=False).count()

    def clean(self, *args, **kwargs):
        if self.is_event_based:
            if not self.fallback_commodity:
                raise ValidationError({
                    'fallback_commodity': _('If this commodity is time-based '
                                            '(you have entered an epoch '
                                            'description), you must also set '
                                            'a fallback commodity.')})
            elif self.fallback_commodity.is_event_based:
                raise ValidationError({
                    'fallback_commodity': _('Fallback commodities may not '
                                            'themselves be event-based.')})
        elif self.fallback_commodity:
            raise ValidationError({
                'fallback_commodity': _('Fallback commodity cannot be set if '
                                        'this commodity is seasonal (i.e. you '
                                        'have not entered an epoch '
                                        'description.')})
        return super().clean(*args, **kwargs)


# A manually curated list of commodity mapping overrides used because there are
# no clear one-to-one mappings based on string similarity for several common
# customer inputs.
#
# E.g. An input of "Cow" should not map to "Cow Peas" but based on string
# similarity alone it might do.
COMMODITY_MAP_OVERRIDES = {
    "cow": "dairy cow",
    "cows": "dairy cow",
    "chicken": "indigenous chickens",
    "chickens": "indigenous chickens",
}


# Memoization cache for the function below. Exposed so it can be cleared from tests.
COMMODITY_MAP_CACHE = cachetools.TTLCache(maxsize=10, ttl=120)


@cachetools.cached(COMMODITY_MAP_CACHE)
def get_commodity_map(commodity_type: str) -> Dict[str, Commodity]:
    """
    Constructs dict name -> Commodity, using both long and short names.
    Memoized to avoid hitting the database over and over again. TTL to refresh from time to time
    in case new commodities were added.
    """
    commodities = Commodity.objects.filter(commodity_type=commodity_type)
    commodity_map = {c.name.lower(): c for c in commodities}
    commodity_map.update({c.short_name.lower(): c for c in commodities})
    return commodity_map
