import sentry_sdk
from dateutil.relativedelta import relativedelta
from psycopg2.extras import DateRange

from django.contrib.gis.db import models
from django.contrib.postgres.fields import DateRangeField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedBase


class WeatherArea(TimestampedBase):
    # GeoDjango-specific: a geometry field (PolygonField), and
    # overriding the default manager with a GeoManager instance.
    poly = models.PolygonField(unique=True, geography=True)

    def __str__(self):
        xmin, ymin, xmax, ymax = self.poly.extent
        return "{}, {}".format(xmin, ymin)


class ForecastDay(TimestampedBase):
    target_date = models.DateField()
    area = models.ForeignKey('WeatherArea', on_delete=models.CASCADE)

    def __init__(self, *args, **kwarg):
        super().__init__(*args, **kwarg)
        sentry_sdk.capture_message(f"ForecastDay being instantiated.")
        raise DeprecationWarning(f"ForecastDay is deprecated. Use CountyForecast as a replacement.")

    def __str__(self):
        return "{}, {}".format(self.area, self.target_date)

    class Meta:
        unique_together = 'target_date', 'area'
        ordering = ('target_date', )

    @property
    def provider(self):
        return self.json['provider']


class WeatherForecast(TimestampedBase):
    """ A historically class used to store weather forecasts for re-use, either for sending out
    a WeatherForecastSentSMS, or combining into a Market and Weather OutgoingSMS.
    """

    start_date = models.DateField()
    end_date = models.DateField()
    weather_area = models.ForeignKey('WeatherArea', on_delete=models.CASCADE)
    text = models.CharField(max_length=160)

    class Meta:
        unique_together = ('start_date', 'weather_area')

    def __init__(self, *args, **kwarg):
        super().__init__(*args, **kwarg)
        sentry_sdk.capture_message(f"WeatherForecast being instantiated.")
        raise DeprecationWarning(f"WeatherForecast is deprecated. Use CountyForecast as a replacement.")


def _this_month(date=None):
    """
    Return date range for the current month suitable for DateRangeField
    start is inclusive and end is exclusive.
    """
    date = date or timezone.now().date()
    start = date.replace(day=1)
    end = start + relativedelta(months=1)
    return [start, end]


class CountyForecast(TimestampedBase):
    """
    dates has a GIST index applied manually using a migration
    """

    dates = DateRangeField(
        default=_this_month,
        help_text=_(
            "Range of dates the forecast covers. Start is inclusive, end is exclusive"
        ),
    )
    category = models.ForeignKey(
        "customers.CustomerCategory",
        on_delete=models.CASCADE,
        related_name="weather_forecasts",
        blank=True,
        null=True,
    )
    county = models.ForeignKey(
        "world.Border",
        on_delete=models.CASCADE,
        related_name="weather_forecasts",
        blank=False,
        null=False,
    )
    premium_only = models.BooleanField(
        default=True,
    )
    text = models.CharField(max_length=160)
    sent = models.BooleanField(
        default=False,
        db_index=True,
    )

    def __str__(self):
        if isinstance(self.dates, DateRange):
            start = self.dates.lower
            end = self.dates.upper
        elif isinstance(self.dates, list):
            start = self.dates[0]
            end = self.dates[1]

        if self.category is not None:
            return "{} + {} from {} to {}".format(
                self.county, self.category, start, end
            )
        else:
            return "{} from {} to {}".format(
                self.county, start, end
            )
