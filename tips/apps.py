from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class TipsConfig(AppConfig):

    name = 'tips'

    def ready(self):
        from actstream import registry
        from .signals import handlers  # noqa: F401

        registry.register(self.get_model('TipSent'))
        registry.register(self.get_model('TipSeries'))
        registry.register(self.get_model('TipSeriesSubscription'))

        post_save.connect(handlers.handle_tipseries_subscription,
                          'tips.TipSeriesSubscription')
        post_delete.connect(handlers.handle_tipseries_unsubscription,
                            'tips.TipSeriesSubscription')
