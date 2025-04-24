from django.template import Library, Node, Variable
from django.template.base import VariableDoesNotExist

import logging
logger = logging.getLogger(__name__)

register = Library()


@register.filter(name='dict_value')
def dict_value(d: dict, k: str):
    """Returns the value of a given key from a dictionary."""
    return d.get(k)
