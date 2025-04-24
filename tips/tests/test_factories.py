from core.test.cases import TestCase

from ..models import Tip, TipSeries, TipSent, TipSeriesSubscription
from .factories import TipFactory, TipSentFactory, TipSeriesFactory, TipSeriesSubscriptionFactory


class TipsFactoryTestCase(TestCase):
    def test_can_create_tip_from_factory(self):
        TipFactory()
        self.assertEqual(1, Tip.objects.count())

    def test_can_create_tipseries_from_factory(self):
        TipSeriesFactory()
        self.assertEqual(1, TipSeries.objects.count())

    def test_can_create_tipsent_from_factory(self):
        TipSentFactory()
        self.assertEqual(1, TipSent.objects.count())

    def test_can_create_tipseriessubscription_from_factory(self):
        TipSeriesSubscriptionFactory()
        self.assertEqual(3, TipSeriesSubscription.objects.count())  # the customer creation creates 2 subscriptions
