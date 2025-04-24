from datetime import date
from unittest import skip
from core.test.cases import TestCase

from agri.tests.factories import CommodityFactory
from agri.models import Commodity
from markets.tests.factories import MarketFactory
from markets.models import Market
from tips.tests.factories import TipSeriesFactory
from tips.models import TipSeries

from ..models import Customer, CustomerPhone
from .factories import CustomerCategoryFactory, CustomerFactory, CustomerPhoneFactory, PremiumCustomerFactory


class CustomerFactoryTestCase(TestCase):
    def test_can_create_customer_from_factory(self):
        CustomerFactory()
        self.assertEqual(1, Customer.objects.count())

    def test_create_customer_creates_phone(self):
        CustomerFactory()
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(1, CustomerPhone.objects.count())

    def test_blank_customer_has_phone_but_no_subscriptions(self):
        customer = CustomerFactory(blank=True)
        self.assertEqual(0, customer.markets.count())
        self.assertEqual(1, customer.subscriptions.count())
        self.assertEqual('Free', customer.subscriptions.first().type.name)
        self.assertEqual(1, CustomerPhone.objects.count())

    def test_default_customer_has_correct_setup(self):
        customer = CustomerFactory()

        self.assertTrue(customer.is_registered)
        self.assertIsNotNone(customer.date_registered)

        self.assertEqual(1, customer.phones.count())
        self.assertEqual(1, CustomerPhone.objects.count())

        self.assertEqual(2, customer.market_subscriptions.count())
        market_sub1 = customer.market_subscriptions.order_by('pk').first()
        market_sub2 = customer.market_subscriptions.order_by('pk').last()
        self.assertEqual(customer, market_sub1.customer)
        self.assertEqual(customer, market_sub2.customer)
        self.assertIsNotNone(market_sub1.market)
        self.assertIsNotNone(market_sub2.market)
        self.assertFalse(market_sub1.market.is_main_market)
        self.assertFalse(market_sub2.market.is_main_market)
        self.assertIsNotNone(market_sub1.backup)
        self.assertIsNotNone(market_sub2.backup)
        self.assertTrue(market_sub1.backup.is_main_market)
        self.assertTrue(market_sub2.backup.is_main_market)

        self.assertEqual(2, customer.tip_subscriptions.count())
        tip_sub1 = customer.tip_subscriptions.order_by('pk').first()
        tip_sub2 = customer.tip_subscriptions.order_by('pk').last()
        self.assertEqual(customer, tip_sub1.customer)
        self.assertEqual(customer, tip_sub2.customer)
        self.assertIsNotNone(tip_sub1.series)
        self.assertIsNotNone(tip_sub2.series)
        self.assertGreater(tip_sub1.start.date(), date(2017, 1, 1))
        self.assertGreater(tip_sub2.start.date(), date(2017, 1, 1))
        self.assertFalse(tip_sub1.ended)
        self.assertFalse(tip_sub2.ended)

    def test_no_markets_customer_has_correct_market_setup(self):
        customer = CustomerFactory(has_no_markets=True)
        self.assertEqual(0, customer.market_subscriptions.count())

    def test_commodities_but_no_markets_customer_has_correct_market_setup(self):
        maize = CommodityFactory(name='Maize', crop=True)
        customer = CustomerFactory(
            has_no_markets=True,
            has_no_tips=True,
            commodities=[maize]
        )
        self.assertEqual(0, customer.market_subscriptions.count())
        self.assertEqual(1, customer.commodities.count())
        self.assertEqual(maize.name,customer.commodities.first().name)

    def test_no_backups_customer_has_correct_market_setup(self):
        customer = CustomerFactory(has_no_backup_markets=True)
        self.assertEqual(2, customer.market_subscriptions.count())
        market_sub1 = customer.market_subscriptions.first()
        market_sub2 = customer.market_subscriptions.last()
        self.assertEqual(customer, market_sub1.customer)
        self.assertEqual(customer, market_sub2.customer)
        self.assertIsNotNone(market_sub1.market)
        self.assertIsNotNone(market_sub2.market)
        self.assertFalse(market_sub1.market.is_main_market)
        self.assertFalse(market_sub2.market.is_main_market)
        self.assertIsNone(market_sub1.backup)
        self.assertIsNone(market_sub2.backup)

    def test_can_create_customer_from_factory_with_categories(self):
        customer = CustomerFactory(
            categories=CustomerCategoryFactory.create_batch(2))

        self.assertEqual(customer.categories.count(), 2)


    @skip("CommoditySubscription is deprecated")
    def test_no_commodities_customer_has_correct_setup(self):
        customer = CustomerFactory(has_no_commodity_subscriptions=True)
        self.assertEqual(0, customer.commodity_subscriptions.count())
        self.assertEqual(0, customer.commoditysubscription_set.count())
        self.assertEqual(2, customer.market_subscriptions.count())

    def test_unregistered_customer_has_correct_setup(self):
        customer = CustomerFactory(unregistered=True)
        self.assertFalse(customer.is_registered)
        self.assertIsNone(customer.date_registered)
        self.assertEqual(0, customer.market_subscriptions.count())

    def test_can_add_commodities(self):
        commodities = CommodityFactory.create_batch(4)
        count = len(commodities)
        customer = CustomerFactory(
            blank=True,
            commodities=commodities
        )
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(count, Commodity.objects.count())
        self.assertEqual(count, customer.commodities.count())
        self.assertEqual(0, customer.market_subscriptions.count())

    def test_can_add_markets(self):
        markets = MarketFactory.create_batch(4)
        count = len(markets)
        customer = CustomerFactory(
            blank=True,
            add_market_subscriptions=markets
        )
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(count, Market.objects.count())
        self.assertEqual(count, customer.market_subscriptions.count())

    def test_can_add_tips(self):
        tipseries = TipSeriesFactory.create_batch(4)
        count = len(tipseries)
        customer = CustomerFactory(
            blank=True,
            add_tip_subscriptions=tipseries
        )
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(count, TipSeries.objects.count())
        self.assertEqual(count, customer.tip_subscriptions.count())

    def test_can_add_single_phone_str(self):
        customer = CustomerFactory(
            blank=True,
            add_phones=['+256720123456']
        )
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(2, CustomerPhone.objects.count())
        self.assertEqual(2, customer.phones.count())

    def test_can_add_multiple_phone_strs(self):
        customer = CustomerFactory(
            blank=True,
            add_phones=['+256720123456', '+256720123457', '+256720123458', '+256720123459']
        )
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(5, CustomerPhone.objects.count())
        self.assertEqual(5, customer.phones.count())


class PremiumCustomerFactoryTestCase(TestCase):
    def test_can_create_premium_customer_from_factory(self):
        self.assertEqual(0, Customer.objects.count())
        self.assertEqual(0, Customer.objects.premium().count())
        premium_customer = PremiumCustomerFactory()
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(1, Customer.objects.premium().count())

    def test_default_customer_has_correct_setup(self):
        customer = PremiumCustomerFactory()

        self.assertTrue(customer.is_registered)
        self.assertIsNotNone(customer.date_registered)

        self.assertEqual(2, customer.market_subscriptions.count())
        market_sub1 = customer.market_subscriptions.order_by('pk').first()
        market_sub2 = customer.market_subscriptions.order_by('pk').last()
        self.assertEqual(customer, market_sub1.customer)
        self.assertEqual(customer, market_sub2.customer)
        self.assertIsNotNone(market_sub1.market)
        self.assertIsNotNone(market_sub2.market)
        self.assertFalse(market_sub1.market.is_main_market)
        self.assertFalse(market_sub2.market.is_main_market)
        self.assertIsNotNone(market_sub1.backup)
        self.assertIsNotNone(market_sub2.backup)
        self.assertTrue(market_sub1.backup.is_main_market)
        self.assertTrue(market_sub2.backup.is_main_market)

        # A premium subscription should have been created
        self.assertEqual(1, customer.subscriptions.filter(type__name='Premium').count())
        # A free subscription should have been created
        self.assertEqual(1, customer.subscriptions.filter(type__name='Free').count())
        # There should be one premium customer
        self.assertEqual(1, Customer.objects.premium().count())
        self.assertEqual(customer.id, Customer.objects.premium().first().id)
