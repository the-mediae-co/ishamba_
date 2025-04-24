import re

from django import template
from django.utils.encoding import force_str
from django.utils.functional import keep_lazy_text

register = template.Library()


@keep_lazy_text
def strip_lines(value):
    """
    Returns the given text with newlines stripped
    """
    return force_str(value).replace('\n', '')


@keep_lazy_text
def collapse_whitespace(value):
    """
    Returns the given text with whitespace collapsed to single spaces
    """
    return re.sub(r'[\s]+', ' ', force_str(value))


class OnelinerNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context).strip()
        stripped = strip_lines(output)
        return collapse_whitespace(stripped) + '\n'


@register.tag
def oneliner(parser, token):
    """
    Removes newlines and collapses whitespace to single spaces in text content

    Example usage::
        {% oneliner %}
        Hello
        I am a fish
        {% endoneliner %}

    Would return::
        HelloI am a fish
    """
    nodelist = parser.parse(('endoneliner',))
    parser.delete_first_token()
    return OnelinerNode(nodelist)
