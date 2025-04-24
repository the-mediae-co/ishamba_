from unittest import skip
from unittest.mock import call, patch

from django.conf import settings

from core.test.cases import TestCase

from gateways.africastalking.testing import activate_success_response

from agri.tests.factories import CommodityFactory
from customers.models import CommoditySubscription, Customer
from customers.tests.factories import CustomerFactory, PremiumCustomerFactory, SubscriptionFactory
from markets import constants
from markets.delivery import MarketPriceSender
from markets.models import MarketPrice
from markets.tasks import send_freemium_market_prices, send_market_price_sms
from markets.tests.factories import MarketFactory
from sms.models import SMSRecipient, OutgoingSMS

from .utils import CreateMarketPricesMixin


class MarketPriceSenderTestCase(CreateMarketPricesMixin, TestCase):
    def setUp(self):
        """ Create a range of customers (and their associated objects) to be
        used in individual test methods.
        """
        super().setUp()
        self.markets = MarketFactory.create_batch(4)

        for name in ('Chickens', 'Maize', 'Beans', 'Millet'):
            # Repeating old behaviour of Chickens being a crop
            setattr(self, name.lower(), CommodityFactory(name=name, crop=True))

        # customers with all required fields
        self.customer_1 = CustomerFactory(
            blank=True,
            commodities=[self.chickens, self.maize],
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )
        self.customer_2 = CustomerFactory(
            blank=True,
            commodities=[self.beans, self.millet],
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )
        # copies markets and commodity subscriptions from self.customer_2
        self.copycat_of_customer_2 = CustomerFactory(
            blank=True,
            commodities=[self.beans, self.millet],
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )
        # previously subscribed and then de-registered customer
        self.inactive_customer = CustomerFactory(
            blank=True,
            commodities=[self.beans, self.millet],
            add_market_subscriptions=[self.markets[0], self.markets[1]],
            is_registered=False
        )
        self.new_customer = CustomerFactory(
            unregistered=True
        )
        # customers without various fields
        self.has_no_markets = CustomerFactory(
            commodities=[self.chickens, self.maize],
            has_no_markets=True,
        )
        self.has_no_commodities = CustomerFactory(
            add_market_subscriptions=[self.markets[0], self.markets[1]],
            commodities=None,
            has_no_tips=True,  # TipSeriesFactory creates commodities
        )
        self.has_no_location = CustomerFactory(
            blank=True,
            commodities=[self.chickens, self.maize],
            add_market_subscriptions=[self.markets[0], self.markets[1]],
            location=None,
        )
        # QuerySet of active customers with all required fields populated
        self.base_active_customers = Customer.objects.filter(
            pk__in=[self.customer_1.pk, self.customer_2.pk]
        )

        # QuerySet of all active subscribers including those with missing
        # fields
        self.all_active_customers = Customer.objects.filter(pk__in=[
            self.customer_1.pk,
            self.customer_2.pk,
            self.copycat_of_customer_2.pk,
            self.has_no_markets.pk,
            self.has_no_commodities.pk,
            self.has_no_location.pk,
        ])

        self.default_sender = MarketPriceSender()

    def test_different_mpms_with_no_prices_for_one_market(self):
        """
        Tests for the regression identified in Issue #40
        Specifically, that MarketPriceMessages were being reused only
        when prices matched, even if the commodities did not.
        """

        one_crop_customer = CustomerFactory(
            blank=True,
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )

        self.create_market_prices(self.customer_2)

        MarketPrice.objects.filter(commodity__short_name='Millet').delete()

        mpm = self.default_sender.get_mpm_for_customer(self.customer_2)
        mpm2 = self.default_sender.get_mpm_for_customer(one_crop_customer)
        self.assertNotEqual(mpm, mpm2)

    def test_market_price_returned_for_customer_with_distinct_amount_market_prices(self):
        self.create_distinct_amount_market_prices(self.customer_1)

        mpm = self.default_sender.get_mpm_for_customer(self.customer_1)

        self.assertIsNotNone(mpm)

    def test_get_existing_mpm_for_customer_generates_three_db_queries(self):
        self.create_distinct_amount_market_prices(self.customer_1)

        # create existing market price message (mpm)
        self.default_sender.get_mpm_for_customer(self.customer_1)

        with self.assertNumQueries(4):
            self.default_sender.get_mpm_for_customer(self.customer_1)

    def test_get_mpm_for_customer_generates_mpm_with_correct_commodities(self):
        self.create_distinct_amount_market_prices(self.customer_1)

        mpm = self.default_sender.get_mpm_for_customer(self.customer_1)

        self.assertIsNotNone(mpm)

        self.assertEqual(
            set(p.commodity for p in mpm.prices.all()),
            set(self.customer_1.commodities.all()))

    def test_get_mpm_for_customer_reuses_mpms(self):
        self.create_distinct_amount_market_prices(self.customer_1)

        mpm1 = self.default_sender.get_mpm_for_customer(self.customer_1)
        mpm2 = self.default_sender.get_mpm_for_customer(self.customer_1)

        self.assertEqual(mpm1.pk, mpm2.pk)

    @skip("CommoditySubscription is deprecated")
    def test_get_mpm_for_customer_returns_none_when_no_valid_subscriptions(self):
        self.create_distinct_amount_market_prices(self.customer_1)

        # disable sending of market prices for customer_1's
        # commodity subscriptions
        CommoditySubscription.objects.filter(
            subscriber=self.customer_1
        ).update(send_market_prices=False)

        mpm = self.default_sender.get_mpm_for_customer(self.customer_1)

        self.assertIsNone(mpm)

    @skip("CommoditySubscription is deprecated")
    def test_get_mpm_for_customer_only_contains_prices_for_enabled_commodity_subscriptions(self):
        self.create_distinct_amount_market_prices(self.customer_1)

        # don't send market prices for customer_1's first commodity
        # subscription
        CommoditySubscription.objects.filter(
            subscriber=self.customer_1,
            commodity=self.customer_1.commodities.first(),
        ).update(send_market_prices=False)

        mpm = self.default_sender.get_mpm_for_customer(self.customer_1)

        # should receive 2 prices
        self.assertEqual(mpm.prices.count(), 2)
        # Different markets, both for the 2nd commodity subscription
        last_commodity = self.customer_1.commodities.last()
        first_price = mpm.prices.first()
        last_price = mpm.prices.last()
        self.assertEqual(first_price.commodity, last_commodity)
        self.assertEqual(last_price.commodity, last_commodity)
        self.assertEqual(first_price.market, self.customer_1.market_subscriptions.order_by('market_id').first().market)
        self.assertEqual(last_price.market, self.customer_1.market_subscriptions.order_by('market_id').last().market)

    @skip("No longer want 'no update' messages sent")
    def test_get_mpm_for_customer_with_no_recent_prices_sends_no_prices_msg(self):
        constants.MARKET_MESSAGES_INCLUDE_NO_UPDATE = True  # Ensure "no update" messages are included

        self.create_expired_market_prices(self.customer_1)

        mpm = self.default_sender.get_mpm_for_customer(self.customer_1)

        # no prices
        self.assertFalse(mpm.prices.all())

        # check message text contains "no prices in the last X weeks" message
        self.assertIn(
            'no prices in the last {} weeks'.format(
                constants.MARKET_PRICE_CUTOFF),
            mpm.text,
        )

    def test_get_mpm_for_customer_with_no_recent_prices_sends_no_msg(self):
        constants.MARKET_MESSAGES_INCLUDE_NO_UPDATE = False  # Ensure "no update" messages are not sent

        self.create_expired_market_prices(self.customer_1)

        mpm = self.default_sender.get_mpm_for_customer(self.customer_1)

        # no message created
        self.assertFalse(mpm)

    def create_market_commodity_pairs(self, customer):
        """
        Return pairs of pks for the given markets and commodity shortnames
        """
        commodities = customer.commodities.values_list('pk', 'short_name')
        markets = customer.market_subscriptions.values_list('market', 'backup')
        return (self.default_sender
                    .combine_markets_and_commodities(markets, commodities))

    def test_get_or_create_market_price_message_matches_prices_exactly(self):
        """ Tests whether or not
        `MarketPriceSender.get_or_create_market_price_message` creates a
        new `MarketPriceMessage` when only prices differs.
        """
        self.create_market_prices(self.customer_1)
        mpm1 = self.default_sender.get_mpm_for_customer(self.customer_1)

        # Get the market/commodity pairs for the same customer
        pairs = self.create_market_commodity_pairs(self.customer_1)
        main_pairs, backup_pairs, all_pairs = pairs

        # Change them slightly, so the match should fail
        all_pairs = list(all_pairs)
        all_pairs.pop()

        mpm2, created = self.default_sender.get_or_create_market_price_message(
            all_pairs,
            self.default_sender.today)

        self.assertTrue(created)
        self.assertNotEqual(mpm1.pk, mpm2.pk)

    @activate_success_response
    @skip('Market prices are now decomposable into multiple messages')
    def test_market_price_string_failure_doesnt_result_in_sending_anything(self):
        customers = Customer.objects.filter(pk=self.customer_1.pk)

        sender = MarketPriceSender(customers=customers)

        self.create_long_stringed_market_prices(self.customer_1)

        sender.send_messages()

        self.assertEqual(SMSRecipient.objects.count(), 0)  # nothing was sent

    def test_send_market_prices_function_returns_error_free_with_no_prices(self):
        """ Integration test sending market prices (without weather) via celery
        task (executed eagerly).
        """
        for c in Customer.objects.all():
            self.create_market_prices(c)

        send_freemium_market_prices.delay()

        # Result should be two here as although there are four calls to
        # `MarketPriceSentSMS.send()` (i.e. four customers messaged) there are
        # only two distinct market and commodity pairings.
        self.assertEqual(2, OutgoingSMS.objects.count())

        # Check only those customers with the correctly populated fields are

    @activate_success_response
    @patch("celery.app.task.denied_join_result")
    def test_market_prices_sent_with_common_amounts(self, mocked_denied_join):
        for customer in self.base_active_customers:
            self.create_common_amount_market_prices(customer)

        sender = MarketPriceSender(customers=self.base_active_customers)

        sender.send_messages()
        # two customers received market prices
        self.assertEqual(SMSRecipient.objects.count(), 2)

    @activate_success_response
    @skip('Market prices are now decomposable into multiple messages')
    def test_market_price_string_failure_doesnt_interrupt_all(self):
        self.create_long_stringed_market_prices(self.customer_1)

        sender = MarketPriceSender(customers=self.base_active_customers)

        sender.send_messages()

        # only one sent sms sent as customer_1's market prices are
        # too long to fit into 160 char sms
        self.assertEqual(SMSRecipient.objects.count(), 1)

    @skip("CommoditySubscription is deprecated")
    @activate_success_response
    @patch("celery.app.task.denied_join_result")
    def test_market_prices_only_sent_if_commodity_subscription_requires_so_1(self, mocked_denied_join):
        for customer in self.base_active_customers:
            self.create_distinct_amount_market_prices(customer)

        # don't send messages for customer_1's commodity
        # subscriptions
        CommoditySubscription.objects.filter(
            subscriber=self.customer_1
        ).update(send_market_prices=False)

        sender = MarketPriceSender(customers=self.base_active_customers)

        sender.send_messages()

        self.assertEqual(SMSRecipient.objects.count(), 1)  # only one customer received market prices

    @skip("CommoditySubscription is deprecated")
    @activate_success_response
    @patch("celery.app.task.denied_join_result")
    def test_market_prices_only_sent_if_commodity_subscription_requires_so_2(self, mocked_denied_join):
        """ only null one of the customer's commodity subscriptions, still
        expect an SMS, but it should fail to mention the non-price-subscribed
        commodity
        """
        # don't send market prices for customer_1's first commodity
        # subscription
        CommoditySubscription.objects.filter(
            subscriber=self.customer_1,
            commodity=self.chickens,
        ).update(send_market_prices=False)

        for customer in self.base_active_customers:
            self.create_distinct_amount_market_prices(customer)

        sender = MarketPriceSender(customers=self.base_active_customers)
        sender.send_messages()

        # two customers received market prices
        self.assertEqual(2, SMSRecipient.objects.count())

        # Customer 1's SMS only mentions one commodity
        text1 = SMSRecipient.objects.get(
            recipient=self.customer_1).message.text

        self.assertNotIn(self.chickens.name, text1)
        self.assertIn(self.maize.name, text1)
        self.assertIn(
            self.customer_1.market_subscriptions.first().market.short_name, text1)

        # Customer 2's SMS mentions both their subscribed commodities and both markets
        text2 = SMSRecipient.objects.get(
            recipient=self.customer_2).message.text

        for commodity in self.customer_2.commodities.all():
            self.assertIn(commodity.name, text2)
        self.assertIn(
            self.customer_2.market_subscriptions.first().market.short_name,
            text2)

    @activate_success_response
    @patch("celery.app.task.denied_join_result")
    def test_market_prices_sent_only_to_active_customers(self, mocked_denied_join):
        for c in Customer.objects.all():
            self.create_market_prices(c)

        send_freemium_market_prices.delay()

        qs = (Customer.objects.should_receive_messages()
                              .can_receive_market_prices())

        customer_ids = set(qs.values_list('pk', flat=True))

        recipient_ids = set(
            SMSRecipient.objects.values_list('recipient__pk', flat=True))

        self.assertEqual(customer_ids, recipient_ids)
        self.assertEqual(SMSRecipient.objects.count(), qs.count())

    @activate_success_response
    @patch("celery.app.task.denied_join_result")
    def test_four_commodity_subscriptions(self, mocked_denied_join):
        customer = PremiumCustomerFactory(
            blank=True,
            commodities=[self.chickens, self.maize, self.beans, self.millet],
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )
        SubscriptionFactory(customer=customer)

        self.create_distinct_amount_market_prices(customer)

        mpm = self.default_sender.get_mpm_for_customer(customer)

        send_market_price_sms.delay(TestCase.get_test_schema_name(), mpm.pk, customer)

        # This might send multiple individual SMS messages due to paging/splitting,
        # but there should be exactly one SentSMS object.
        self.assertEqual(1, OutgoingSMS.objects.count())
