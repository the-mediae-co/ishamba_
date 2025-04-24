from os import path
from django.apps import AppConfig
from django.utils.autoreload import autoreload_started

def my_watchdog(sender, **kwargs):
    from django.conf import settings
    sender.watch_dir(settings.PROJECT_ROOT, '.env')


class CoreConfig(AppConfig):

    name = 'core'

    def ready(self):
        autoreload_started.connect(my_watchdog)
