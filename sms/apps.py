from django.apps import AppConfig


class SMSConfig(AppConfig):

    name = 'sms'

    def ready(self):
        from actstream import registry
        registry.register(self.get_model('IncomingSMS'))
        registry.register(self.get_model('OutgoingSMS'))
