from django import template
from django.utils.functional import keep_lazy_text
from customers.constants import JOIN_METHODS, STOP_METHODS

from customers.models import Customer

register = template.Library()


@register.filter(is_safe=True)
@keep_lazy_text
def join_description(value: str = '?'):
    """
    Returns explanation text for the given method of joining
    """
    return dict(JOIN_METHODS.choices).get(value)


@register.filter(is_safe=True)
@keep_lazy_text
def stop_description(value: str = '?'):
    """
    Returns explanation text for the given method of stopping
    """
    return dict(STOP_METHODS.choices).get(value)
