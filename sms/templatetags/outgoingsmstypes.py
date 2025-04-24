from django import template
from django.utils.functional import keep_lazy_text

from sms.constants import OUTGOING_SMS_TYPE, SMS_TYPE_ICON_MAP

register = template.Library()


@register.filter(is_safe=True)
@keep_lazy_text
def sms_type_description(value):
    """
    Returns explanation text for the given OutgoingSMS type
    """
    return dict(OUTGOING_SMS_TYPE.choices).get(value)


@register.filter(is_safe=True)
@keep_lazy_text
def sms_type_icon(value):
    """
    Returns the icon associated with the OutgoingSMS type
    """
    return SMS_TYPE_ICON_MAP.get(value)
