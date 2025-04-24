from django.utils import timezone
from core.test.cases import TestCase

from customers.tests.factories import CustomerFactory
from .factories import TipSeriesFactory
from ..models import TipSeriesSubscription


class TipModelTestCase(TestCase):

    def test_add_subscription_works(self):
        customer = CustomerFactory(blank=True)
        tip_series = TipSeriesFactory()
        tip_subscription = TipSeriesSubscription.objects.create(
            customer=customer,
            series=tip_series,
            start=timezone.now(),
            ended=False,
        )
        self.assertEqual(1, customer.tip_subscriptions.count())
        self.assertEqual(tip_series.name, tip_subscription.series.name)
        self.assertEqual(tip_subscription.series.name, customer.tip_subscriptions.first().series.name)
        self.assertEqual(customer, customer.tip_subscriptions.first().customer)
        self.assertFalse(customer.tip_subscriptions.first().ended)
        self.assertEqual(1, customer.commodities.count())
        self.assertEqual(customer.commodities.first(), customer.tip_subscriptions.first().series.commodity)
