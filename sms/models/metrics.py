import logging
import decimal

from core.models import TimestampedBase
from django.db import models

from sms.constants import OUTGOING_SMS_TYPE


logger = logging.getLogger(__name__)


class DailyOutgoingSMSSummary(TimestampedBase):
    """
    A class to represent one day's summary of Outgoing SMS messages. There is
    a unique DailyOutgoingSMSSummary instance created for each combination
    of country/date/message_type/gateway. The other fields like count and
    cost are the aggregated statistics for the country/date/message_type/gateway
    """
    # The country this summary is relevant to. Default to 1, which is Kenya
    country = models.ForeignKey('world.Border', blank=False, default=1,
                                related_name='+',
                                on_delete=models.CASCADE)
    # The day that this summary is for
    date = models.DateField(blank=False, null=False)
    # The type of outgoing sms that this summary is for
    message_type = models.CharField(max_length=8, blank=False, null=False,
                                    choices=OUTGOING_SMS_TYPE.choices,
                                    default=OUTGOING_SMS_TYPE.UNKNOWN)
    # The carrier / MNO / gateway that these messages were sent via
    gateway_name = models.CharField(max_length=120, blank=False, null=False, default='?')

    # Total number of messages of this type on this day
    count = models.PositiveIntegerField(blank=False, null=False)
    # Total cost of all messages sent of this type in this day. Max = 99,999,999.99 units
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=decimal.Decimal(0.00))
    # The units that the total cost is expressed in (e.g. ksh, usd, etc.) lower case
    cost_units = models.CharField(max_length=8, blank=False, null=False, default='?')
    # A json field to hold any additional data (e.g. user stats, message list, etc.)
    extra = models.JSONField(blank=True, default=dict)

    class Meta:
        verbose_name = "Daily OutgoingSMS Summary"
        verbose_name_plural = "Daily OutgoingSMS Summaries"
        constraints = [
            models.UniqueConstraint(fields=['country', 'date', 'gateway_name', 'message_type'],
                                    name='unique_country_date_gateway_message_type'),
        ]
        indexes = [
            models.Index(fields=['date'], name='date_index'),
            models.Index(fields=['gateway_name'], name='gateway_name_idx'),
        ]
