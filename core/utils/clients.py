from functools import wraps
from typing import Callable

from django.core.exceptions import ImproperlyConfigured
from django_tenants.utils import schema_context

from core.models import Client


def client_setting(setting_name: str, schema_name: str = None, country_name: str = None):
    if not schema_name:
        from django.db import connection
        schema_name = connection.schema_name
    try:
        client = Client.objects.get(schema_name=schema_name)
    except Client.DoesNotExist:
        raise ImproperlyConfigured(f"Missing setting {setting_name} for client {schema_name} in country {country_name}")

    localized_setting_name = f"{setting_name}_{country_name}" if country_name else setting_name
    # First look up localized setting
    setting_value = getattr(client, localized_setting_name, None)
    if setting_value is None:
        setting_value = getattr(client, setting_name, None)

    if setting_value is None:
        # If the key was not found, perhaps the setting_name is localized. Try removing the county names.
        from world.models import Border
        country_names = Border.objects.filter(level=0).values_list('name', flat=True)
        for country_name in country_names:
            setting_name = setting_name.replace(f'_{country_name}', '')
        setting_value = getattr(client, setting_name, None)

    if setting_value is None:
        raise ImproperlyConfigured(f"Missing setting {setting_name} for client {schema_name} in country {country_name}")
    return setting_value


def get_all_clients():
    return list(Client.objects.all())


def with_schema_context(func: Callable[[str,], None]):
    """Wraps function of single argument (schema name) to be invoked under schema context"""
    @wraps(func)
    def wrapped_func(schema_name: str, *args, **kwargs):
        with schema_context(schema_name):
            return func(schema_name, *args, **kwargs)

    return wrapped_func
