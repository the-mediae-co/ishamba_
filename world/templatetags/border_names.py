from django import template

from world.models import Border, BorderLevelName

import logging
logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def border_names(country: Border, level: int) -> str:
    """Returns the name that a country uses to describe an administrative boundary level."""
    if isinstance(country, Border):
        country = country.name
    if not 0 <= level <= 5:
        raise ValueError(f"BorderLevelName.level of {level} not between 0 and 5.")
    try:
        name = BorderLevelName.objects.get(country=country, level=level).name
    except BorderLevelName.DoesNotExist as e:
        name = f"border{level}"
    return name
