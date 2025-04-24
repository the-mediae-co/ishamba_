from dateutil.relativedelta import relativedelta
from dateutil.rrule import MO, TH
from time import strftime
import datetime
from django.utils import formats, translation, timezone


def first_day_of_iso_week_date_year(date):
    """
    Returns the first day of week 1 of the given date's year in the ISO week
    date system.

    As the ISO week date calendar starts with the week containing the first
    Thursday of the year, we work backwards to the previous Monday.
    """
    first_thursday = date + relativedelta(
        year=date.isocalendar()[0],  # get the correct ISO calendar year
        month=1, day=1,  # 1 January of that year
        weekday=TH,  # get the next Thursday
    )
    prev_monday = first_thursday + relativedelta(weekday=MO(-1))
    return prev_monday


def midnight(dt):
    """ For a given datetime return midnight that day. """
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def localised_date_formatting_string() -> str:
    # Get the localized strftime format string
    format_strings = formats.get_format("DATE_INPUT_FORMATS", lang=translation.get_language())
    if format_strings:
        # format_codes is an array of localised strftime strings, the first
        # of which is day, month, year
        format_string = format_strings[0]

    return format_string or "%d/%m/%Y"


def localised_time_formatting_string() -> str:
    # Get the localized strftime format string
    format_strings = formats.get_format("TIME_INPUT_FORMATS", lang=translation.get_language())
    if format_strings:
        # format_codes is an array of localised strftime strings, the first
        # of which is hours, minutes, seconds (without fractions)
        format_string = format_strings[0]

    return format_string or "%H:%M:%S"


def localise_date_string(date: datetime.date) -> str:
    format_string = localised_date_formatting_string()
    return strftime(format_string, date)


def localise_time_string(time: datetime.datetime) -> str:
    format_string = localised_time_formatting_string()
    return strftime(format_string, time)


def _one_year_from_today():
    return timezone.now().date() + relativedelta(years=+1)


def _get_current_date():
    return timezone.now().date()
