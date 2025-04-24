from urllib.parse import urlencode
from django import template
from django.db.models import BLANK_CHOICE_DASH

from tasks.models import Task
from tasks.tags import collapse_tags as collapse_tags_func

register = template.Library()


@register.filter
def get_classname(obj):
    """ Returns the class name of passed `obj`.
    """
    return obj.__class__.__name__


@register.filter
def action_to_string(tag, field):
    """ Converts status or priority integer value to it's corresponding display
    value (i.e. mimics the functionality of `obj.get_PROPERTY_display()`)
    """
    if tag == '':
        return BLANK_CHOICE_DASH[0][1]
    # The following are special cases for the way we used to categorize statuses.
    # The action stream still has remnants of these in its history, so we map
    # to new names in the UI here.
    elif tag == 'in_progress':
        return Task.STATUS.progressing
    elif tag == 'resolved':
        return Task.STATUS.closed_resolved
    elif tag == 'unresolved':
        return Task.STATUS.closed_unresolved
    else:
        return Task.STATUS[tag] if field == 'status' else Task.PRIORITY[tag]


@register.filter
def collapse_tags(tags):
    """ Takes a QuerySet of Tags and renders them as a string.
    """
    return collapse_tags_func(tags)


@register.simple_tag(takes_context=True)
def last_page_url(context):
    """ Returns an encoded url corresponding to the current filter + 'page=9999'
    """
    request = context.get('request', None)
    if request:
        url_dict = request.GET.dict()
        url_dict.update({'page': 9999})
        return '?' + urlencode(url_dict)
    return ""
