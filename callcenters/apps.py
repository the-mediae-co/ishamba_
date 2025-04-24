from django.apps import AppConfig


class CallcentersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'callcenters'

    def ready(self) -> None:
        import callcenters.signals
