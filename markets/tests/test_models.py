from datetime import date

from django.utils.timezone import now

from core.test.cases import TestCase

from agri.tests.factories import CommodityFactory
from markets.models import MarketPriceMessage, generate_mpm_hash

from ..delivery import MarketPriceSender
from .factories import MarketFactory, MarketPriceFactory


class GetOrCreateMarketPriceMessageTestCase(TestCase):

    def setUp(self):
        super().setUp()
        # Create markets, commodities, and market prices needed for tests.
        markets = MarketFactory.create_batch(2)
        commodities = CommodityFactory.create_batch(3)
        for i, market in enumerate(markets):
            for j, commodity in enumerate(commodities):
                mp = MarketPriceFactory(market=market, commodity=commodity)
                setattr(self, 'mp_m{}_c{}'.format(i, j), mp)

        self.default_sender = MarketPriceSender()

    def test_basic_non_repeated_usage(self):
        paired_pks = [
            (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
            (self.mp_m1_c0.market.pk, self.mp_m1_c0.commodity.pk),
            (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
        ]
        today = now().date()

        mpm, created = self.default_sender.get_or_create_market_price_message(
            paired_pks=paired_pks,
            target_date=today)
        self.assertTrue(created)
        queryset = MarketPriceMessage.objects.filter(
            hash=generate_mpm_hash(paired_pks, today),
            date=today).distinct()
        self.assertEqual(queryset.count(), 1)

    def test_get_or_create_with_single_m2m_links(self):
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertFalse(created_2)
        self.assertEqual(mpss_1, mpss_2)

    def test_get_or_create_with_two_market_links(self):
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m1_c0.market.pk, self.mp_m1_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m1_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertFalse(created_2)
        self.assertEqual(mpss_1, mpss_2)

    def test_get_or_create_with_two_commodity_links(self):
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
                (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
                (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
            ],
            target_date=now().date())
        self.assertFalse(created_2)
        self.assertEqual(mpss_1, mpss_2)

    def test_get_or_create_with_all_double_m2m_links(self):
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
                (self.mp_m1_c0.market.pk, self.mp_m1_c0.commodity.pk),
                (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
                (self.mp_m1_c0.market.pk, self.mp_m1_c0.commodity.pk),
                (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
            ],
            target_date=now().date())
        self.assertFalse(created_2)
        self.assertEqual(mpss_1, mpss_2)

    def test_get_or_create_with_reordered_m2m_links(self):
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=(
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
                (self.mp_m1_c0.market.pk, self.mp_m1_c0.commodity.pk),
                (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
            ),
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=(
                (self.mp_m1_c0.market.pk, self.mp_m1_c0.commodity.pk),
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m1_c1.market.pk, self.mp_m1_c1.commodity.pk),
            ),
            target_date=now().date())
        self.assertFalse(created_2)
        self.assertEqual(mpss_1, mpss_2)

    def test_get_or_create_with_one_then_two_then_one_m2m_links(self):
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_2)
        self.assertTrue(mpss_1.id < mpss_2.id)
        mpss_3, created_3 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertFalse(created_3)
        self.assertNotEqual(mpss_1, mpss_2)
        self.assertEqual(mpss_1, mpss_3)

    def test_get_or_create_with_two_then_one_then_one_m2m_links(self):
        """ A variation on the previous test case. This breaks an older version
        of the then-called get_or_create_market_price_sent_sms, which sometimes
        found unintentional 'duplicates', and then selected the wrong one, then
        discarded it on further inspection as it wasn't not really a duplicate,
        thus creating a new, actual, duplicate.  The choice was dependent on id
        ordering, hence repeating the above test 'in reverse'.
        """
        mpss_1, created_1 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
                (self.mp_m0_c1.market.pk, self.mp_m0_c1.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_1)
        mpss_2, created_2 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertTrue(created_2)
        self.assertTrue(mpss_1.id < mpss_2.id)
        mpss_3, created_3 = self.default_sender.get_or_create_market_price_message(
            paired_pks=[
                (self.mp_m0_c0.market.pk, self.mp_m0_c0.commodity.pk),
            ],
            target_date=now().date())
        self.assertFalse(created_3)
        self.assertNotEqual(mpss_1, mpss_2)
        self.assertEqual(mpss_2, mpss_3)

    def test_marketpricemessage_hash_matches(self):
        today = now().date()
        hash_1 = generate_mpm_hash(((10, 20), (12, 15)), today)
        hash_2 = generate_mpm_hash(((10, 20), (12, 15)), today)
        self.assertEqual(hash_1, hash_2)

    def test_marketpricemessage_hash_length(self):
        today = now().date()
        hash_1 = generate_mpm_hash(((10, 20), (12, 15)), today)
        self.assertEqual(len(hash_1), 32)

    def test_marketpricemessage_hash_different_pks(self):
        today = now().date()
        hash_1 = generate_mpm_hash(((10, 5), (10, 20)), today)
        hash_2 = generate_mpm_hash(((12, 15), (10, 20)), today)
        self.assertNotEqual(hash_1, hash_2)

    def test_marketpricemessage_hash_different_dates(self):
        d1 = date(year=2016, month=5, day=10)
        d2 = date(year=2016, month=6, day=5)
        hash_1 = generate_mpm_hash(((12, 15), (10, 20)), d1)
        hash_2 = generate_mpm_hash(((12, 15), (10, 20)), d2)
        self.assertNotEqual(hash_1, hash_2)

    def test_marketpricemessage_hash_different_orders(self):
        today = now().date()
        hash_1 = generate_mpm_hash(((12, 15), (10, 20)), today)
        hash_2 = generate_mpm_hash(((10, 20), (12, 15)), today)
        # The order of the pairs shouldn't matter
        self.assertEqual(hash_1, hash_2)

    def test_marketpricemessage_hash_storage(self):
        today = now().date()
        hash_1 = generate_mpm_hash(((12, 15), (10, 20)), today)

        MarketPriceMessage.objects.create(hash=hash_1, date=today)

        mpm = MarketPriceMessage.objects.get(hash=hash_1)
        self.assertEqual(mpm.hash, hash_1)

    def test_create_market_price_message(self):
        today = now().today()
        paired_pks = ((10, 15), (5, 7))

        mpm, created = (self.default_sender
                            .get_or_create_market_price_message(paired_pks,
                                                                today))
        self.assertTrue(created)

    def test_get_market_price_message(self):
        today = now().today()
        paired_pks = ((10, 15), (5, 7))

        mpm, created = (self.default_sender
                            .get_or_create_market_price_message(paired_pks,
                                                                today))

        mpm2, created2 = (self.default_sender
                              .get_or_create_market_price_message(paired_pks,
                                                                  today))

        self.assertFalse(created2)
        self.assertEqual(mpm, mpm2)
