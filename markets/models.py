import pickle as pickle
import hashlib
import os
import random
import uuid
from decimal import Decimal

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from agri.models.base import Commodity
from core.logger import log
from core.models import TimestampedBase
from customers.models import Customer
from markets import constants


class Market(TimestampedBase):
    """ Market places where goods are bought and sold.
    """
    name = models.CharField(max_length=160, unique=True)
    short_name = models.CharField(max_length=6, unique=True)

    is_main_market = models.BooleanField(
        default=False,
        help_text="Are price updates are reliably regularly received?")

    # GeoDjango-specific geometry field (PointField)
    location = models.PointField(geography=True)

    class Meta:
        ordering = 'name',

    def __str__(self):
        name = self.name
        if self.is_main_market:
            name += " (main)"
        return name

    @property
    def descriptive_name(self):
        if self.is_main_market:
            return "{} (main market)".format(self.name)
        return self.name


class MarketPrice(TimestampedBase):
    """ The record of a retrieved price, unique by market, commodity, date.
    """
    market = models.ForeignKey('Market', on_delete=models.CASCADE)
    commodity = models.ForeignKey('agri.Commodity', on_delete=models.CASCADE)
    date = models.DateField(_('date'),
                            help_text="The date this price was retrieved at "
                            "the market.")
    source = models.CharField(_('source'),
                              max_length=30)
    amount = models.PositiveSmallIntegerField(_('amount'),
                                              help_text="The number of [unit]s"
                                              " that this price is for.")
    price = models.PositiveSmallIntegerField(_('price'),
                                             help_text="In Kenyan shillings.")
    unit = models.CharField(_('unit'),
                            max_length=30)

    def __str__(self):
        try:
            return "{market} {date} {commodity}: {price}".format(
                market=self.market,
                date=self.date,
                commodity=self.commodity,
                price=self.price,
            )
        except (Commodity.DoesNotExist, Market.DoesNotExist):
            # When django-import-export does a dry run the related objects
            # haven't been saved yet.
            # See: https://github.com/django-import-export/django-import-export/issues/439
            return "{date}: {price}".format(date=self.date, price=self.price)

    class Meta:
        unique_together = ('date', 'market', 'commodity')

    @property
    def unit_price(self):
        """ Returns a quantized Decimal instance.
        """
        return (Decimal(self.price) / Decimal(self.amount)).quantize(
            Decimal('1')
        )

    @property
    def display_amount(self):
        """ Returns 'each' if it's just per unit, otherwise a formatted string
            e.g. '90 kg'.
        """
        if self.amount == 1 and self.unit == 'unit':
            return "each"

        return "{amount} {unit}".format(amount=self.amount,
                                        unit=self.display_unit)

    @property
    def display_unit(self):
        """ Returns a more SI-like kg.
        """
        try:
            return constants.DISPLAY_UNITS[self.unit.lower()]
        except KeyError:
            msg = ('Imported market price exists with unrecognised unit '
                   'string: {}'.format(self.unit))
            log.warning(msg, extra={'market_price': self})
            return self.unit


def generate_mpm_hash(paired_pks=None, date=None):
    if not paired_pks and not date:
        random.seed(os.urandom(128))
        return uuid.uuid4().hex
    pickled = pickle.dumps((sorted(paired_pks), date))
    return hashlib.md5(pickled).hexdigest()


class MarketPriceMessage(TimestampedBase):
    """
    The pre-formatted string from a combination of MarketPrice records, for
    sending in a MarketPriceSentSMS, or combined market price and weather SMS.
    """

    hash = models.CharField(max_length=32, unique=True)
    text = models.TextField()
    prices = models.ManyToManyField('MarketPrice')
    date = models.DateField()

    def __str__(self):
        return "{} {}".format(self.id, self.date)


class MarketSubscription(TimestampedBase):
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='market_subscriptions'
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='primary_subscriptions'
    )
    backup = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='backup_subscriptions',
        blank=True,
        null=True
    )
    commodity = models.ForeignKey(
        'agri.Commodity',
        on_delete=models.CASCADE,
        related_name='market_subscriptions',
        blank=False,
        null=True
    )

    class Meta:
        unique_together = ('customer', 'market', 'commodity')
        verbose_name = "Market subscription"

    def __str__(self):
        try:
            str_value = "{} <--> {}".format(self.customer, self.market)
        except Customer.DoesNotExist:
            # django-import-export runs force_str(instance) on
            # MarketSubscription instances before they have been
            # created and raises an Exception as self.customer isn't populated.
            return f'{self.market}'

        if self.backup:
            str_value += " (backup: {})".format(self.backup)
        return str_value

    def clean(self):
        # Restrict number of subscriptions
        max_allowed = self.customer.subscriptions.get_usage_allowance('markets')

        if self.pk is None and self.customer.market_subscriptions.count() >= max_allowed:
            raise ValidationError("You can only set {} market subscriptions"
                                  " for this customer".format(max_allowed))

        # If a market exists...
        if self.market:
            # Ensure that backup markets are set
            if not self.market.is_main_market and self.backup is None:
                raise ValidationError("You must set a backup, as {} is not a main"
                                      " market".format(self.market))
            # Make sure the backup market is a main market
            if self.backup and not self.backup.is_main_market:
                raise ValidationError("The backup market must be a main market")
