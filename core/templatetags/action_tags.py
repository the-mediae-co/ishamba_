from django import template
from django.conf import settings
from django.template.defaulttags import date as datefilter
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from ..constants import ACTION_TEMPLATES
from ..utils.actions import get_action_agent

register = template.Library()


@register.simple_tag
def render_action_description(action):
    """
    Each action type will be rendered differently using a template.
    The templates are defined in ACTION_TEMPLATES.
    """
    ctx = {
        'actor': action.actor,
        'verb': action.verb,
        'target': action.target,
        'action_object': action.action_object,
        'action': action
    }
    if action.data:
        ctx.update(action.data)

    ctx['agent'] = get_action_agent(action)

    desc_template = ACTION_TEMPLATES.get(action.verb)
    if desc_template:
        return mark_safe(render_to_string(desc_template, ctx))
    else:
        return str(action)


@register.simple_tag
def render_timestamp(action):
    if (now() - action.timestamp).days < 2:
        timestamp = datefilter(action.timestamp, settings.DATETIME_FORMAT)
        template = '<span title="{timestamp}">{timesince} ago</span>'
        return mark_safe(template.format(timestamp=timestamp,
                                         timesince=action.timesince()))
    return action.timestamp
