

import json
import math
import re
from bisect import bisect
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction

from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.template.loader import render_to_string
from django.utils.timezone import now

import requests
from dateutil.parser import parse

from weather import constants
from weather.api import awhere_constants
from weather.models import ForecastDay, WeatherArea
from world.utils import point_in_supported_area

aw = None


def get_awhere_session(refresh=False):
    global aw

    if refresh or not aw:
        service = awhere_constants.SERVICES['auth']
        payload = {
            'uid': settings.AWHERE_USERNAME,
            'pwd': settings.AWHERE_PASSWORD,
        }
        aw = requests.Session()
        # TODO some better SSL checking so we can remove the verify=False kwarg
        # below
        r = aw.post(service['url'], data=payload, verify=False)
        r.raise_for_status()  # returns None if all's well, or raises HTTPError

    return aw


def api_try(method, *args, **kwargs):
    """ If the aWhere API returns 401 we assume it's because the session has
    expired. This DRYs the process of retrying the authentication step.
    """
    aw = get_awhere_session()
    the_callable = getattr(aw, method)
    try:
        r = the_callable(*args, **kwargs)
        r.raise_for_status()
    except requests.HTTPError:
        if r.status_code == 401:  # Unauthorised (sp.)
            # We assume a 401 is due to session-expiry.
            aw = get_awhere_session(refresh=True)
            the_callable = getattr(aw, method)
            r = the_callable(*args, **kwargs)
        # We want to re-raise if we encounter any further errors, including
        # still getting a 401 status code.
        r.raise_for_status()

    return r


def get_forecast_days(location, start_date=now().date(), *args, **kwargs):
    """ A wrapper around get_forecast_data and store_forecast_data.
        Returns a queryset of ForecastDay objects.
    """
    forecast_data = get_forecast_data(location, start_date, *args, **kwargs)
    forecast_days = store_forecast_data(forecast_data)
    return ForecastDay.objects.filter(pk__in=[fd.pk for fd in forecast_days])


def get_forecast_data(location, start_date, *args, **kwargs):
    """ Returns json.
    """
    # some other possible query_string parameters:
    # endDate=None,
    # plantingDate=None,
    # gddMethod=awhere_constants.GDD_METHOD_STANDARD,
    # baseTemp=None,
    # maxTempCap=None,
    # minTempCap=None
    service = awhere_constants.SERVICES['forecast']
    payload = {
        'latitude': location.y,
        'longitude': location.x,
        'startDate': start_date,
        'endDate': start_date + timedelta(days=awhere_constants.FORECAST_DAYS),
        'attribute': awhere_constants.FORECAST_ATTRIBUTES,
    }
    payload.update(awhere_constants.OPTIONAL_INPUTS)
    payload.update(kwargs)

    resp = api_try('get', service['url'], params=payload)
    # NB this is .raise_for_status()ed in api_try

    forecast_data = json.loads(resp.content)

    return forecast_data


def store_forecast_data(data):
    """ Accepts json. Creates a ForecastDay object for each json entry. Returns
        a list of ForecastDay objects.
    """
    forecast_days = []

    for entry in data:
        # get the correct weather_area, or create one
        point = Point(entry['longitude'], entry['latitude'])
        weather_area, created = get_or_create_weather_area(point)

        # get, for overwriting, any previous forecasts for this day/location
        # combination, otherwise create
        forecast_day, __ = ForecastDay.objects.get_or_create(
            target_date=parse(entry['date']),
            area=weather_area,
        )

        # note the source of this blob
        entry['provider'] = 'aWhere'

        forecast_day.json = entry
        forecast_day.save()

        forecast_days.append(forecast_day)

    return forecast_days


def get_or_create_weather_area(point):
    """ Get_or_create wrapper for succinct reuse. This is based on the
    assumption that a 'poly__covers' lookup is preferred over
    possible duplicate polygon generation followed by the model's native
    get_or_create method.

    We only use the slower duplicate polygon approach if the point argument is
    on the border of two or more areas (and causes MultipleObjectsReturned).

    Returns an (object, created) tuple, as expected.
    """
    try:
        return WeatherArea.objects.get(poly__covers=point), False
    except WeatherArea.DoesNotExist:
        box = create_awhere_box_for_location(point)
        return WeatherArea.objects.create(poly=box), True
    except WeatherArea.MultipleObjectsReturned:
        point = create_awhere_box_for_location(point).point_on_surface
        return WeatherArea.objects.get(poly__covers=point), False


def create_awhere_box_for_location(point, resolution_mins=5,
                                   point_is_supported=True):
    """ Given a Point instance, returns an approximately-square Polygon
        instance containing the point. The 'corner' points of the 'box' will be
        at coordinates:

            (x   * r, y   * r)
            (x+1 * r, y   * r)
            (x+1 * r, y+1 * r)
            (x   * r, y+1 * r)

        where x and y are integers, and r = resolution_mins/60.
    """
    # sanity check - see whether this point is in a supported area
    if point_is_supported and not point_in_supported_area(point):
        raise ValueError('Location is not in a supported area')

    lon = rational_floor(point.x, resolution_mins)
    lat = rational_floor(point.y, resolution_mins)

    res = Fraction(resolution_mins, 60)
    box = Polygon.from_bbox((lon, lat, lon + res, lat + res))

    return box


def rational_floor(measurement, resolution_mins):
    """ Given a measurement in decimal degrees, and a resolution in arcminutes,
        returns the highest multiple of the resolution less than the
        measurement.

        Uses Decimal and Fraction to avoid floating point errors.
    """
    if not isinstance(measurement, Fraction):
        measurement = Fraction(Decimal(str(measurement)))
    resolution_degrees = Fraction(resolution_mins, 60)
    exact_multiple = measurement / resolution_degrees
    integer_multiple = math.floor(exact_multiple)
    return float(integer_multiple * resolution_degrees)


def format_weather_forecast_text(forecastdays):
    """
    Returns a formatted weather message for a given queryset of forecastdays.

    NOTE: We expect all forecastdays to be for the same location.

    This is in weather.api.awhere because the available fields are
    provider-dependent.
    """
    # Some initial values
    rain_likely_days = []
    min_temps = []
    max_temps = []

    for fc_day in forecastdays:
        try:
            conditions = fc_day.json['conditions'][0]
        except IndexError:
            continue

        if conditions is not None:
            max_temp = conditions.get('maxTemperature')
            if max_temp is not None:
                max_temps.append(max_temp)

            min_temp = conditions.get('minTemperature')
            if min_temp is not None:
                min_temps.append(min_temp)

            precip_percent = conditions.get('precipPercent')
            # conditions['precipPercent'] is the percentage likelihood of rain
            if precip_percent is not None:
                if precip_percent >= constants.RAIN_LIKELY_THRESHOLD:
                    rain_likely_days.append(fc_day.target_date)

    try:
        max_max_temp = max(max_temps)
        min_min_temp = min(min_temps)
    except ValueError:
        max_max_temp = None
        min_min_temp = None
        rain_likely_string = ''
        have_data = False
    else:
        have_data = True
        rain_likely_string = format_rain_likely_days(rain_likely_days)

    context = {
        'have_data': have_data,
        'max_max_temp': max_max_temp,
        'min_min_temp': min_min_temp,
        'rain_likely_string': rain_likely_string,
    }

    message = render_to_string('weather/sms/weather_forecast_sms.txt', context)
    message = re.sub(r'[\n\s]+', ' ', message.strip())

    return message


def format_rain_likely_days(rain_likely_days):
    """ Takes a list of dates for which rain is likely, and returns a readable
    string, combining consecutive days.
    """
    if rain_likely_days:
        output = 'Rain likely '
        mid_stream = False
        i = rain_likely_days.pop(0)
        # always print the first
        output += constants.SHORT_DAY_NAMES[i.weekday()]
        for i_plus_1 in rain_likely_days:
            if i_plus_1 == i + timedelta(days=1):
                # this is consecutive to the previous
                if not mid_stream:
                    output += '-'
                    mid_stream = True
            else:
                if mid_stream:
                    # a previous string has ended, print the last day
                    output += constants.SHORT_DAY_NAMES[i.weekday()]
                output += ', ' + constants.SHORT_DAY_NAMES[i_plus_1.weekday()]
                mid_stream = False
            i = i_plus_1
        # if we were in the middle of a consecutive sequence, we won't have
        # printed the last
        if mid_stream:
            output += constants.SHORT_DAY_NAMES[i.weekday()]
        output += '.'
        return output
    else:
        return "Rain not likely this week."


def summarise_max_temp(max_temps_list):
    """ Calculates mean max temp (__future__ division), then use bisect to look
    it up from a prepared list of temp/description tuples.

    No longer used. 'Refactored' here for posterity.
    """
    if max_temps_list:
        mean_max_temp = sum(max_temps_list) / len(max_temps_list)
        temp_ranges = constants.TEMP_RANGES
        temp_ranges.sort(key=lambda t: t[0])
        keys = [r[0] for r in temp_ranges]
        return temp_ranges[bisect(keys, mean_max_temp) - 1][1]
    else:
        return ""
