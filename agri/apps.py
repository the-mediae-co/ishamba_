from django.apps import AppConfig


class AgriConfig(AppConfig):

    name = 'agri'

    def ready(self):
        from actstream import registry
        registry.register(self.get_model('Commodity'))
