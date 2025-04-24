from time import gmtime, strftime

from django import template

from core.utils.datetime import localised_time_formatting_string

import logging
logger = logging.getLogger(__name__)

register = template.Library()


@register.filter
def format_time(secs: int) -> str:
    """Returns a formatted time string given a number of seconds."""
    if not secs or secs == 0:
        return '00:00:00'

    return strftime(localised_time_formatting_string(), gmtime(secs))
