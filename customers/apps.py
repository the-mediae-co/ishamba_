from django.apps import AppConfig
from django.db.models.signals import post_save


class CustomersConfig(AppConfig):

    name = 'customers'

    def ready(self):
        from actstream import registry
        from .signals import handlers

        registry.register(self.get_model('Customer'))

        post_save.connect(handlers.handle_customer_post_save,
                          'customers.Customer')
