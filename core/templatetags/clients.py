from django import template

from ..utils import clients


register = template.Library()


@register.simple_tag
def client_setting(setting_name, schema_name=None):
    return clients.client_setting(setting_name, schema_name=schema_name)
