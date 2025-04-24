from typing import Union, List, Tuple
from datetime import date
import itertools

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.template.loader import get_template
from django.utils.timezone import localtime, now
from django.db.models.query import QuerySet

from dateutil.relativedelta import relativedelta

from agri.models.base import Commodity
from core.utils.models import queryset_iterator
from customers.models import Customer
from markets import constants
from markets.models import (MarketPrice,
                            MarketPriceMessage, generate_mpm_hash)
from markets.tasks import send_market_price_sms


class MarketPriceSender(object):
    """
    Handles the delivery of market price messages.
    """

    def __init__(self, *args, **kwargs):
        # Use supplied Customer queryset or all customers
        self.customers = kwargs.pop('customers', Customer.objects.all())

        self.customers = (self.customers.should_receive_messages())

        # load the market price sms template
        self.market_price_template = get_template(
            'markets/sms/market_price_sms.txt')

        self.today = localtime(now()).date()

        # we're not interested in stale market prices
        cutoff_date = self.today - relativedelta(weeks=constants.MARKET_PRICE_CUTOFF)

        # we prepare a prices queryset for all the ensuing code, so that all
        # the 'latest' lookups are pre-done
        self.prices = self.get_latest_prices(cutoff_date)

    @staticmethod
    def get_latest_prices(cutoff_date):
        """
        A separate method, so it can be unit-tested.
        """
        return (MarketPrice.objects.filter(date__gte=cutoff_date)
                .order_by('market__id', 'commodity__id', '-date')
                .distinct('market', 'commodity'))

    def send_messages(self):
        """
        Sends a market price message for each customer in `self.customers`.
        """
        for chunk in queryset_iterator(self.customers):
            for customer in chunk:
                mpm = self.get_mpm_for_customer(customer)

                if mpm:
                    send_market_price_sms.delay(connection.tenant.schema_name, mpm, customer)

    # def get_commodities_for_customer(self, customer: Customer) -> Union[QuerySet, List[Tuple[int, str]]]:
    #     """
    #     Return list of pk, shortname tuples for the commodities a given
    #     customer is subscribed to.
    #     """
    #     return Commodity.objects.filter(
    #         commoditysubscription__subscriber=customer.pk,
    #         commoditysubscription__send_market_prices=True
    #     ).values_list('pk', 'short_name')

    def combine_markets_and_commodities(self, markets, commodities: QuerySet):
        """
        Finds all the combinations of the given market and commodity pks.

        Args:
            markets: A list of tuples with main and backup market pks.
            commodities: A list of tuples with commodity pk and short_names.

        Returns:
            A 3-tuple of tuples containing (market, commodity) tuples. For
            main markets, backup markets and all markets respectively.
        """
        commodity_pks = [pk for pk, __ in commodities]
        main_pks, backup_pks = list(zip(*markets))

        # values_list will return None if unset, so we need to filter
        main_pks = filter(None, main_pks)
        backup_pks = filter(None, backup_pks)

        # Find all combinations of market and commodity pks
        main_paired = tuple(itertools.product(main_pks, commodity_pks))
        backup_paired = tuple(itertools.product(backup_pks, commodity_pks))
        all_paired = main_paired + backup_paired
        return main_paired, backup_paired, all_paired

    def get_mpm_for_customer(self, customer: Customer) -> MarketPriceMessage:
        """
        Retrieves or generates a MarketPriceMessage for a given customer
        based on the current date and their market/commodity subscriptions.
        """
        # commodities = self.get_commodities_for_customer(customer)
        # TODO: Instead of searching all customer commodities, each market
        # price subscription needs to contain a list of the commodities for that market
        commodities = customer.commodities.values_list('pk', 'short_name')
        markets = customer.market_subscriptions.values_list('market', 'backup')

        # check if the customer has valid commodity subscriptions else bail
        if not commodities or not markets:
            return None

        # Find all combinations of market and commodity pks
        pairs = self.combine_markets_and_commodities(markets, commodities)
        main_pairs, backup_pairs, all_pairs = pairs

        # Get all prices for the all the combinations
        # NOTE: Price fetching cannot be hoisted out it's own function as
        # doing so incurs multiple additional DB queries.
        all_prices = self.prices.extra(
            where=['(market_id,commodity_id) IN %s'],
            params=[all_pairs])

        # Ignore backup pairs when there is a main pair
        ignored = []
        zipped_pairs = itertools.zip_longest(main_pairs, backup_pairs)
        for price in all_prices:
            for main, backup in zipped_pairs:
                if (price.market_id, price.commodity_id) == main:
                    if backup:
                        ignored.append(backup)

        # Filter out all the ignored pairs
        prices = [price for price in all_prices
                  if not (price.market_id, price.commodity_id) in ignored]

        # if no markets have price updates, bail
        if not prices:
            return None

        # If an identical message already exists, we should use that
        mpm, created = self.get_or_create_market_price_message(all_pairs,
                                                               self.today)

        if created:
            # If it is a new message then create the content
            ctx = self.generate_context_for_mpm_text(prices, commodities)
            # TODO: Set creator_id correctly here
            mpm.text = self.render_message(ctx)
            mpm.save(update_fields=['text'])
            mpm.prices.add(*prices)

        return mpm

    def generate_context_for_mpm_text(self, prices: List[MarketPrice], commodities: QuerySet):
        """
        Generates the context for a market price message based on
        the lists of prices and commodities provided.

        Args:
            prices: list of MarketPrice objects
            commodities: list of tuples, (pk, short_name)

        Returns:
            A context dict, mapping prices to commodities. For example:

            {
                'commodities': {
                    'Dry Maize': {
                        'display_amount': '',
                        'markets': [
                            {
                                'market': 'Nairobi',
                                'price': 500,
                                'currency': 'KSH',
                                'display_amount': '200 kg'
                            },
                            {
                                'market': 'Mombasa',
                                'price': 400,
                                'currency': 'KSH',
                                'display_amount': '110 kg'
                            }
                        ],
                    },
                    'Sorghum': {
                        'display_amount': '110 kg',
                        'markets': [
                            {
                                'market': 'Mombasa',
                                'price': 300,
                                'currency': 'KSH',
                                'display_amount': '110 kg'
                            }
                        ]
                    },
                },
                'least_accurate_date': a_datetime_object,
                'sources': set(['NAFIS']),
                'cutoff': 4,
            }

        """
        # initialise variables
        display_amounts = set()
        sources = set()
        least_accurate_date = self.today

        with_prices = []
        without_prices = []

        for commodity_pk, commodity_short_name in commodities:
            commodity_prices = []
            commodity_context = {
                'short_name': commodity_short_name,
            }

            for mp in prices:
                # skip market prices that aren't related to this commodity
                if mp.commodity_id != commodity_pk:
                    continue

                commodity_prices.append(mp)
                display_amounts.add(mp.display_amount)
                sources.add(mp.source)
                least_accurate_date = min(least_accurate_date, mp.date)

            if len(display_amounts) == 1:
                # We have a common display_amount string
                commodity_context['common_quantity'] = display_amounts.pop()

            if commodity_prices:
                commodity_context['prices'] = commodity_prices
                with_prices.append(commodity_context)
            elif constants.MARKET_MESSAGES_INCLUDE_NO_UPDATE:
                without_prices.append(commodity_context)

        return {
            'commodities_with_prices': with_prices,
            'commodities_without_prices': without_prices,
            'cutoff': constants.MARKET_PRICE_CUTOFF,
            'least_accurate_date': least_accurate_date,
            'sources': sorted(sources),
        }

    def render_message(self, context):
        return self.market_price_template.render(context).strip()

    def get_or_create_market_price_message(self, paired_pks, target_date: date):
        """
        Return a new or existing MarketPriceMessage using the given
        market and commodity pks and target_date to lookup with a hash.

        Args:
            paired_pks: List of tuples with market and commodity pks
            target_date: A date object

        Return:
            A new or existing MarketPriceMessage object
        """
        mpm_hash = generate_mpm_hash(paired_pks, target_date)
        defaults = {'date': target_date}
        return MarketPriceMessage.objects.get_or_create(hash=mpm_hash,
                                                        defaults=defaults)
