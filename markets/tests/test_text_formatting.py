from datetime import date
from unittest.mock import patch

from django.utils.timezone import now

from core.test.cases import TestCase

from dateutil.relativedelta import relativedelta

import markets
from agri.tests.factories import CommodityFactory
from customers.tests.factories import CustomerFactory
from markets import constants
from markets.delivery import MarketPriceSender
from markets.models import MarketPrice

from .factories import MarketFactory, MarketPriceFactory


@patch.object(markets.delivery.MarketPriceSender, 'render_message')
class MarketPriceTextFormattingTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.markets = MarketFactory.create_batch(4)

        # commodities
        self.maize = CommodityFactory(name='Maize', crop=True)
        # NOTE: This doesn't make sense as chickens isn't a crop (they're
        # seasonal livestock), however, they were defined as a crop in the old
        # fixtures and we don't receive `MarketPrice`s for seasonal livestock.
        self.chickens = CommodityFactory(name='Chickens', crop=True)

        # customers
        self.subscribed_customer_1 = CustomerFactory(
            blank=True,  # We don't want the CustomerFactory to create commodities and markets
            commodities=[self.maize, self.chickens],     # Add the ones we want
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )

        self.subscribed_with_backups_1 = CustomerFactory(
            blank=True,  # We don't want the CustomerFactory to create commodities and markets
            commodities=[self.maize, self.chickens],     # Add the ones we want
            add_market_subscriptions=[self.markets[0], self.markets[1]],
        )
        subs = self.subscribed_with_backups_1.market_subscriptions.order_by('pk').first()
        subs.backup = self.markets[2]
        subs.save(update_fields=['backup'])
        subs = self.subscribed_with_backups_1.market_subscriptions.order_by('pk').last()
        subs.backup = self.markets[3]
        subs.save(update_fields=['backup'])

        # market_subscriptions1__market = self.markets[0],
        # market_subscriptions2__market = self.markets[1],
        # market_subscriptions1__backup = self.markets[2],
        # market_subscriptions2__backup = self.markets[3]

        # job and message delivery obj
        self.sender = MarketPriceSender()

    def test_setup_is_correct(self, mock_format_price_text):
        """ Asserts that the commodity and market/backup market subscriptions
        for the two test case customers match up. Handy for debugging for these
        to correspond.
        """
        self.assertEqual(
            self.subscribed_customer_1.market_subscriptions.first().market,
            self.subscribed_with_backups_1.market_subscriptions.first().market
        )
        self.assertEqual(
            self.subscribed_customer_1.market_subscriptions.last().market,
            self.subscribed_with_backups_1.market_subscriptions.last().market
        )
        self.assertEqual(self.chickens.name, 'Chickens')

    def test_date_correct_fully_populated(self, mock_format_price_text):
        mock_format_price_text.return_value = 'test string'

        MarketPriceFactory(
            market=self.markets[0],
            commodity=self.chickens,
            expired=True)

        m0_chickens_recent_price = MarketPriceFactory(
            market=self.markets[0],
            commodity=self.chickens,
            recent=True)

        MarketPriceFactory(
            market=self.markets[0],
            commodity=self.chickens,
            old=True)

        m0_maize_recent_price = MarketPriceFactory(
            market=self.markets[0],
            commodity=self.maize,
            recent=True)

        self.sender.get_mpm_for_customer(self.subscribed_customer_1)

        mock_format_price_text.assert_called_once_with(
            {
                'commodities_with_prices': [
                    {
                        'short_name': self.chickens.short_name,
                        'prices': [m0_chickens_recent_price],
                        'common_quantity': '1 KSH'
                    },
                    {
                        'short_name': self.maize.short_name,
                        'prices': [m0_maize_recent_price],
                        'common_quantity': '1 KSH'
                    }
                ],
                'commodities_without_prices': [],
                'cutoff': constants.MARKET_PRICE_CUTOFF,
                'sources': ['RECENT'],
                'least_accurate_date': m0_chickens_recent_price.date  # earliest
            },
        )

    def test_backup_markets_are_used(self, mock_format_price_text):
        mock_format_price_text.return_value = 'test string'

        MarketPriceFactory(
            market=self.markets[0],
            commodity=self.chickens,
            expired=True)

        m0_backup_chickens_recent_price = MarketPriceFactory(
            market=self.markets[2],
            commodity=self.chickens,
            recent=True,
            source='RECENT BACKUP')

        m0_maize_old_price = MarketPriceFactory(
            market=self.markets[0],
            commodity=self.maize,
            old=True)

        # More recent that m0_maize_old_price but not used as is only backup
        MarketPriceFactory(
            market=self.markets[2],
            commodity=self.maize,
            recent=True)

        self.sender.get_mpm_for_customer(self.subscribed_customer_1)

        mock_format_price_text.assert_called_with(
            {
                'commodities_without_prices': [
                    {
                        'short_name': self.chickens.short_name,
                    },
                ],
                'commodities_with_prices': [
                    {
                        'short_name': self.maize.short_name,
                        'prices': [m0_maize_old_price],
                        'common_quantity': '1 KSH'
                    }
                ],
                'cutoff': constants.MARKET_PRICE_CUTOFF,
                'sources': ['OLD'],
                'least_accurate_date': m0_maize_old_price.date
            },
        )

        self.sender.get_mpm_for_customer(self.subscribed_with_backups_1)

        mock_format_price_text.assert_called_with(
            {
                'commodities_with_prices': [
                    {
                        'short_name': self.chickens.short_name,
                        'prices': [m0_backup_chickens_recent_price],
                        'common_quantity': '1 KSH'
                    },
                    {
                        'short_name': self.maize.short_name,
                        'prices': [m0_maize_old_price],
                        'common_quantity': '1 KSH'
                    }
                ],
                'commodities_without_prices': [],
                'cutoff': constants.MARKET_PRICE_CUTOFF,
                'sources': ['OLD', 'RECENT BACKUP'],
                'least_accurate_date': m0_maize_old_price.date
            },
        )

    def test_backup_markets_are_not_used_when_old_but_still_new_enough_first_choice_prices_exist(self, mock_format_price_text):
        mock_format_price_text.return_value = 'test string'
        constants.MARKET_MESSAGES_INCLUDE_NO_UPDATE = True  # Temporarily override to test no-update message

        MarketPriceFactory(
            market=self.markets[0],
            commodity=self.chickens,
            expired=True,
            source='M0 TOO OLD')

        # Used as main market price too old
        m0_backup_chickens_recent_price = MarketPriceFactory(
            market=self.markets[2],
            commodity=self.chickens,
            recent=True,
            source='M0 BACKUP RECENT')

        # Used
        m1_chickens_old_price = MarketPriceFactory(
            market=self.markets[1],
            commodity=self.chickens,
            old=True,
            source='M1 OLD')

        # Not used. Newer, but main market is new enough.
        MarketPriceFactory(
            market=self.markets[3],
            commodity=self.chickens,
            recent=True,
            source='M1 BACKUP RECENT')

        self.sender.get_mpm_for_customer(self.subscribed_with_backups_1)

        mock_format_price_text.assert_called_with(
            {
                'commodities_with_prices': [
                    {
                        'short_name': self.chickens.short_name,
                        'prices': [m1_chickens_old_price, m0_backup_chickens_recent_price],
                        'common_quantity': '1 KSH'
                    },
                ],
                'commodities_without_prices': [
                    {
                        'short_name': self.maize.short_name,
                    }
                ],
                'cutoff': constants.MARKET_PRICE_CUTOFF,
                'sources': ['M0 BACKUP RECENT', 'M1 OLD'],
                'least_accurate_date': m1_chickens_old_price.date
            },
        )


class GetOnlyLatestPricesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.markets = MarketFactory.create_batch(2)
        self.commodities = CommodityFactory.create_batch(3)

    def test_latest_prices_only_returned(self):
        today = now().date()
        for commodity in self.commodities:
            for market in self.markets:
                MarketPriceFactory(recent=True,
                                   commodity=commodity,
                                   market=market)
                MarketPriceFactory(old=True,
                                   commodity=commodity,
                                   market=market)

        # test two created for every combination
        self.assertEqual(MarketPrice.objects.count(),
                         len(self.markets) * len(self.commodities) * 2)

        cutoff_date = today - relativedelta(weeks=constants.MARKET_PRICE_CUTOFF)
        prices = MarketPriceSender.get_latest_prices(cutoff_date)

        # test only one price retrieved per commodity
        self.assertEqual(prices.count(),
                         len(self.markets) * len(self.commodities))
        for commodity in self.commodities:
            for market in self.markets:
                self.assertEqual(prices.filter(commodity=commodity,
                                               market=market).count(),
                                 1)

        # and they're all the 'RECENT' ones only
        self.assertEqual(set(prices),
                         set(MarketPrice.objects.filter(source='RECENT')))


class MarketPriceMessageRenderingTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.nairobi = MarketFactory(short_name='NAI')
        self.nakuru = MarketFactory(short_name='NAK')
        self.mombasa = MarketFactory(short_name='MOM')
        self.kisumu = MarketFactory(short_name='KIS')

        self.maize = CommodityFactory(name='Maize', crop=True)
        self.carrots = CommodityFactory(name='Carrots', crop=True)
        self.beans = CommodityFactory(name='Beans', crop=True)
        self.tomatoes = CommodityFactory(name='Tomatoes', crop=True)

        self.date = date(year=2016, month=9, day=19)

        self.sender = MarketPriceSender()

    def test_with_two_prices_two_markets(self):

        m0_carrots_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.carrots,
            date=self.date,
            recent=True)

        m0_maize_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.maize,
            date=self.date,
            recent=True)

        m1_carrots_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.carrots,
            price=2000,
            date=self.date,
            recent=True)

        m1_maize_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.maize,
            price=2500,
            date=self.date,
            recent=True)

        ctx = {
            'commodities_with_prices': [
                {
                    'short_name': 'Chicken',
                    'prices': [m0_carrots_recent_price, m1_carrots_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Maize',
                    'prices': [m0_maize_recent_price, m1_maize_recent_price],
                    'common_quantity': '1 KSH'
                },
            ],
            'commodities_without_prices': [],
            'cutoff': constants.MARKET_PRICE_CUTOFF,
            'sources': ['RECENT'],
            'least_accurate_date': m0_carrots_recent_price.date  # earliest
        }

        message = self.sender.render_message(ctx)
        self.assertEqual(message, "Prices from RECENT via iShamba (19 Sep).\n"
                                  "Chicken 1 KSH: NAI 1000, MOM 2000.\n"
                                  "Maize 1 KSH: NAI 1000, MOM 2500.")

    def test_with_two_commodities_one_market(self):

        m0_carrots_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.carrots,
            date=self.date,
            recent=True)

        m0_maize_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.maize,
            date=self.date,
            recent=True)

        ctx = {
            'commodities_with_prices': [
                {
                    'short_name': 'Chicken',
                    'prices': [m0_carrots_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Maize',
                    'prices': [m0_maize_recent_price],
                    'common_quantity': '1 KSH'
                }
            ],
            'commodities_without_prices': [],
            'cutoff': constants.MARKET_PRICE_CUTOFF,
            'sources': ['RECENT'],
            'least_accurate_date': m0_carrots_recent_price.date  # earliest
        }

        message = self.sender.render_message(ctx)
        self.assertEqual(message, ("Prices from RECENT via iShamba (19 Sep).\n"
                                   "Chicken 1 KSH: NAI 1000.\n"
                                   "Maize 1 KSH: NAI 1000."))

    def test_with_four_commodities_two_markets(self):

        m0_carrots_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.carrots,
            date=self.date,
            recent=True)

        m0_maize_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.maize,
            date=self.date,
            recent=True)

        m0_beans_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.beans,
            date=self.date,
            recent=True)

        m0_tomatoes_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.tomatoes,
            price=700,
            date=self.date,
            recent=True)

        m1_carrots_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.carrots,
            price=2000,
            date=self.date,
            recent=True)

        m1_maize_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.maize,
            price=2500,
            date=self.date,
            recent=True)

        m1_beans_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.beans,
            price=2700,
            date=self.date,
            recent=True)

        m1_tomatoes_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.tomatoes,
            price=3250,
            date=self.date,
            recent=True)

        ctx = {
            'commodities_with_prices': [
                {
                    'short_name': 'Chicken',
                    'prices': [m0_carrots_recent_price, m1_carrots_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Maize',
                    'prices': [m0_maize_recent_price, m1_maize_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Beans',
                    'prices': [m0_beans_recent_price, m1_beans_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Tomatoes',
                    'prices': [m0_tomatoes_recent_price, m1_tomatoes_recent_price],
                    'common_quantity': '1 KSH'
                },
            ],
            'commodities_without_prices': [],
            'cutoff': constants.MARKET_PRICE_CUTOFF,
            'sources': ['RECENT'],
            'least_accurate_date': m0_carrots_recent_price.date  # earliest
        }

        message = self.sender.render_message(ctx)
        self.assertEqual(message, ("Prices from RECENT via iShamba (19 Sep).\n"
                                   "Chicken 1 KSH: NAI 1000, MOM 2000.\n"
                                   "Maize 1 KSH: NAI 1000, MOM 2500.\n"
                                   "Beans 1 KSH: NAI 1000, MOM 2700.\n"
                                   "Tomatoes 1 KSH: NAI 700, MOM 3250."))

    def test_with_four_commodities_two_markets_one_missing(self):

        m0_carrots_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.carrots,
            date=self.date,
            recent=True)

        m0_maize_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.maize,
            date=self.date,
            recent=True)

        m0_beans_recent_price = MarketPriceFactory(
            market=self.nairobi,
            commodity=self.beans,
            date=self.date,
            recent=True)

        m1_carrots_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.carrots,
            price=2000,
            date=self.date,
            recent=True)

        m1_maize_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.maize,
            price=2500,
            date=self.date,
            recent=True)

        m1_beans_recent_price = MarketPriceFactory(
            market=self.mombasa,
            commodity=self.beans,
            price=2700,
            date=self.date,
            recent=True)

        ctx = {
            'commodities_with_prices': [
                {
                    'short_name': 'Chicken',
                    'prices': [m0_carrots_recent_price, m1_carrots_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Maize',
                    'prices': [m0_maize_recent_price, m1_maize_recent_price],
                    'common_quantity': '1 KSH'
                },
                {
                    'short_name': 'Beans',
                    'prices': [m0_beans_recent_price, m1_beans_recent_price],
                    'common_quantity': '1 KSH'
                },
            ],
            'commodities_without_prices': [],
            'cutoff': constants.MARKET_PRICE_CUTOFF,
            'sources': ['RECENT'],
            'least_accurate_date': m0_carrots_recent_price.date  # earliest
        }

        message = self.sender.render_message(ctx)
        self.assertEqual(message, ("Prices from RECENT via iShamba (19 Sep).\n"
                                   "Chicken 1 KSH: NAI 1000, MOM 2000.\n"
                                   "Maize 1 KSH: NAI 1000, MOM 2500.\n"
                                   "Beans 1 KSH: NAI 1000, MOM 2700."))
