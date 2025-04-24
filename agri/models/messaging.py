from collections import defaultdict

import sentry_sdk
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MO

from .base import Region, Commodity
from core.models import TimestampedBase
from sms.utils import clean_sms_text


class AgriTipSMS(TimestampedBase):
    commodity = models.ForeignKey('agri.Commodity',
                                  verbose_name=_('Commodity'), on_delete=models.CASCADE)
    region = models.ForeignKey('agri.Region',
                               verbose_name=_('Region'),
                               blank=True,
                               null=True,
                               on_delete=models.SET_NULL
                               )
    number = models.SmallIntegerField(_('number'))
    text = models.CharField(_('text'), max_length=160)

    class Meta:
        verbose_name = _("Agri-tip SMS")
        unique_together = ('commodity', 'region', 'number')

    def __init__(self, *args, **kwarg):
        super().__init__(*args, **kwarg)
        sentry_sdk.capture_message(f"AgriTipSMS being instantiated.")
        raise DeprecationWarning(f"AgriTipSMS is deprecated. Use tips/TipSeries as a replacement.")

    def __str__(self):
        try:
            if self.region is not None:
                return "{region} {comm}, {number}".format(region=self.region,
                                                          comm=self.commodity,
                                                          number=self.number)
            else:
                return "{comm}, {number}".format(comm=self.commodity,
                                                 number=self.number)
        except (Commodity.DoesNotExist, Region.DoesNotExist):
            # When django-import-export does a dry run the related objects
            # haven't been saved yet.
            # See: https://github.com/django-import-export/django-import-export/issues/439
            return str(self.number)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude)

        errors = defaultdict(list)
        # Check the uniqueness constraint when region is None
        if self.region is None:
            exists = AgriTipSMS.objects.filter(region=None,
                                               commodity=self.commodity,
                                               number=self.number).exists()
            if exists:
                errors['__all__'].append(
                    _("Agri-tip SMS with this Commodity, Region (none) and "
                      "Number already exists."))

        # Check the number for seasonal commodities
        if not self.commodity.is_event_based:
            # NOTE: The ISO week date system (used for agri-tip numbering)
            # is a leap week calendar and thus the maximum here is 53 rather
            # than 52 as you might expect from the Gregorian calendar.
            max_number = 53 // settings.AGRI_TIPS_SENDING_PERIOD
            if self.number < 1 or self.number > max_number:
                errors['number'].append(
                    _("Must be between 1 and {} for seasonal "
                      "commodities").format(max_number))

        # Check the region: required for crops, blank for livestock
        if self.commodity.is_livestock and self.region is not None:
            errors['region'].append(
                _("Region must be blank for livestock tips."))
        if self.commodity.is_crop and self.region is None:
            errors['region'].append(
                _("Region must be supplied for crop tips."))

        try:
            self.text = clean_sms_text(self.text, strip=False)  # Don't hide invalid GSM characters from the user
        except ValidationError as e:
            errors.update(e.error_dict)

        if errors:
            raise ValidationError(errors)

    @staticmethod
    def earliest_date_for_relative_tip(epoch_date, tip):
        """
        Return date that is exactly `settings.AGRI_TIPS_SENDING_PERIOD`
        weeks after the first day of the isocalendar week containing
        `epoch_date`. Matches earlier than that are not considered
        suitable for this subscription.
        """
        weeks = settings.AGRI_TIPS_SENDING_PERIOD * tip
        delta = relativedelta(weeks=weeks, weekday=MO(-1))
        return epoch_date + delta
