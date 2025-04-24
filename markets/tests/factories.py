import datetime

import factory.fuzzy
from factory.django import DjangoModelFactory

from .. import constants, models


class MarketFactory(DjangoModelFactory):
    class Meta:
        model = models.Market

    name = factory.Sequence(lambda n: "Market %d" % n)
    short_name = factory.fuzzy.FuzzyText(length=6)
    location = '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}'
    is_main_market = False


class MarketPriceFactory(DjangoModelFactory):
    class Meta:
        model = models.MarketPrice

    market = factory.SubFactory(MarketFactory)
    commodity = factory.SubFactory('agri.tests.factories.CommodityFactory')
    date = factory.LazyFunction(datetime.date.today)
    amount = 1
    price = 1000
    unit = 'KSH'

    class Params:
        recent = factory.Trait(
            source='RECENT'
        )
        old = factory.Trait(
            date=factory.LazyAttribute(
                lambda o: datetime.date.today()
                - datetime.timedelta(days=1)
            ),
            source='OLD'
        )
        expired = factory.Trait(
            date=factory.LazyAttribute(
                lambda o: datetime.date.today()
                - datetime.timedelta(weeks=(constants.MARKET_PRICE_CUTOFF + 1))
            ),
            source='EXPIRED'
        )


class MarketSubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = models.MarketSubscription

    customer = factory.SubFactory('customers.tests.factories.CustomerFactory')
    market = factory.SubFactory(MarketFactory, is_main_market=False)
    backup = factory.SubFactory(MarketFactory, is_main_market=True)
