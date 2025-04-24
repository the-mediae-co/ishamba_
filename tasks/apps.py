from django.apps import AppConfig


class TasksConfig(AppConfig):
    name = 'tasks'

    def ready(self):
        from django.contrib.auth import get_user_model
        from actstream import registry
        from . import receivers  # NOQA

        registry.register(get_user_model())
        registry.register(self.get_model('Task'))
