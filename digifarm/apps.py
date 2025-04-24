from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, register


class DigifarmConfig(AppConfig):
    name = 'digifarm'


REQUIRED_SETTINGS = [
    'DIGIFARM_USERNAME',
    'DIGIFARM_PASSWORD'
]


@register
def missing_settings_check(app_configs, **kwargs):
    errors = []
    for name in REQUIRED_SETTINGS:
        if not hasattr(settings, name):
            errors.append(
                Error(
                    "Missing setting",
                    "Please set {} in your settings".format(name),
                    id="digifarm.E001",
                )
            )

    return errors
