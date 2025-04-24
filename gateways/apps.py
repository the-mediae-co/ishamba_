from django.apps import AppConfig


class GatewaysAppConfig(AppConfig):
    name = 'gateways'
    label = 'gateways'
    verbose_name = 'Mediae gateways'

    def ready(self):
        from . import signals  # NOQA
