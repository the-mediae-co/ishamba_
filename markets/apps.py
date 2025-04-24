from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class MarketConfig(AppConfig):
    name = 'markets'

    def ready(self):
        from actstream import registry
        from .signals import handlers

        registry.register(self.get_model('Market'))
        registry.register(self.get_model('MarketSubscription'))

        post_save.connect(handlers.handle_market_subscription,
                          'markets.MarketSubscription')
        post_delete.connect(handlers.handle_market_unsubscription,
                            'markets.MarketSubscription')
