from core.test.cases import TestCase

from ..models import Market, MarketPrice, MarketSubscription
from .factories import MarketFactory, MarketPriceFactory, MarketSubscriptionFactory


class MarketFactoryTestCase(TestCase):
    def test_can_create_tip_from_factory(self):
        MarketFactory()
        self.assertEqual(1, Market.objects.count())

    def test_can_create_tipseries_from_factory(self):
        MarketPriceFactory()
        self.assertEqual(1, MarketPrice.objects.count())

    def test_can_create_tipseriessubscription_from_factory(self):
        MarketSubscriptionFactory()
        self.assertEqual(3, MarketSubscription.objects.count())  # the customer creation creates 2 subscriptions
