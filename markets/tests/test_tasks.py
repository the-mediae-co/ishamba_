from core.test.cases import TestCase

from ..tasks import send_freemium_market_prices, send_premium_market_prices


class FreemiumTaskTestCase(TestCase):

    def test_no_customers(self):
        # Shouldn't raise an IndexError
        send_freemium_market_prices.delay()


class PremiumTaskTestCase(TestCase):

    def test_no_customers(self):
        # Shouldn't raise an IndexError
        send_premium_market_prices.delay()
