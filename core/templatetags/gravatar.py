import hashlib
from urllib.parse import urlencode

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


# return only the URL of the gravatar
# TEMPLATE USE:  {{ email|gravatar_url:150 }}
@register.filter(takes_context=True)
def gravatar_url(email, size=40):

    return mark_safe("https://www.gravatar.com/avatar/{}?{}".format(
        hashlib.md5(email.lower().encode()).hexdigest(),
        urlencode({'d': settings.GRAVATAR_DEFAULT, 's': str(size)})
    ))


# return an image tag with the gravatar
# TEMPLATE USE:  {{ email|gravatar:150 }}
@register.filter
def gravatar(email, size=40):
    url = gravatar_url(email, size)

    return mark_safe(
        '<img src="{:s}" height="{:d}" width="{:d}">'.format(url, size, size)
    )
