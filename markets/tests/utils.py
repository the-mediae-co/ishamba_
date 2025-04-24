import datetime

from dateutil.relativedelta import relativedelta

from .. import constants
from ..models import MarketPrice


class CreateMarketPricesMixin(object):
    """
    Provides helper methods to create different types of market prices for
    a given customer.

    NOTE: Refactor to use Factory Boy in future.
    """

    def create_market_prices(self, customer, price_date=None,
                             distinct_amounts=False, unit='kg', source='NAFIS'):
        """ Creates market prices for each market and commodity that a
        customer is subscribed to.
        Args:
            customer (Customer): The customer for whom we create the
                `MarketPrice`s.
        Kwargs:
            price_date (datetime.date): The date on which the market price was
                reported (defaults to yesterday).
            distinct_amounts (bool): Whether or not the `MarketPrice.amount`s
                should differ from one another.
            source (string): Price data source identifier.
            unit (string): Unit of amount measurement.
        """
        if price_date is None:
            price_date = datetime.date.today() - datetime.timedelta(days=1)

        prices = []

        for commodity in customer.commodities.all():
            for i, marketsub in enumerate(customer.market_subscriptions.all()):
                price, __ = MarketPrice.objects.get_or_create(
                    market=marketsub.market,
                    commodity=commodity,
                    date=price_date,
                    defaults={
                        'source': source,
                        # if we have a distinct amount scale the amount by i
                        'amount': 100 * i if distinct_amounts else 100,
                        'price': 1100 * (i + 1),
                        'unit': unit,
                    }
                )
                prices.append(price)

        return prices

    def create_distinct_amount_market_prices(self, customer):
        """ Create market prices with distinct amounts for a given customer's
        commodity and market subscription pairs.

        Args:
            customer (Customer): The customer for whom we create the
                `MarketPrice`s with distinct amounts.
        """
        self.create_market_prices(customer, distinct_amounts=True)

    def create_expired_market_prices(self, customer):
        """ Create expired market prices for a given customer's commodity and
        market subscription pairs.

        Args:
            customer (Customer): The customer for whom we create the expired
                `MarketPrice`s.
        """
        after_cutoff = datetime.date.today() - relativedelta(weeks=constants.MARKET_PRICE_CUTOFF + 1)

        self.create_market_prices(customer, price_date=after_cutoff)

    def create_long_stringed_market_prices(self, customer):
        """Create market prices with long unit and source strings for a given
        customer's commodity and market subscription pairs.

        NOTE: This method is somewhat flawed as is *only* guaranteed to
        trigger a message > 160 chars with these fixtures.

        Args:
            customer (Customer): The customer for whom we create the expired
                `MarketPrice`s.
        """
        self.create_market_prices(customer,
                                  source='a' * 30,
                                  unit='b' * 30)

    def create_common_amount_market_prices(self, customer):
        """Create market prices with common amounts (but distinct prices) for a
        given customer's commodity and market subscription pairs.

        Args:
            customer (Customer): The customer for whom we create the common
                amount `MarketPrice`s.
        """
        return self.create_market_prices(customer)
