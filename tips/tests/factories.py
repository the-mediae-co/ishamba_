import datetime

from django.utils import timezone

import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from callcenters.models import CallCenter
from world.models import Border

from .. import models


class TipSeriesFactory(DjangoModelFactory):

    class Meta:
        model = models.TipSeries

    commodity = factory.SubFactory('agri.tests.factories.CommodityFactory')
    name = factory.SelfAttribute('commodity.name')
    start_event = 'The End'
    end_message = 'This is the end, my only friend, the end'
    legacy = True


class TipFactory(DjangoModelFactory):

    class Meta:
        model = models.Tip

    commodity = factory.SubFactory('agri.tests.factories.CommodityFactory')
    delay = factory.Faker('date_time')
    # series = factory.SubFactory(TipSeriesFactory)
    call_center = factory.LazyAttribute(lambda o: CallCenter.objects.first())
    border1 = factory.LazyAttribute(lambda o: Border.kenya_counties.order_by('?').first())

    @factory.lazy_attribute
    def delay(self):
        return datetime.timedelta(days=3)


class TipTranslationFactory(DjangoModelFactory):

    class Meta:
        model = models.TipTranslation

    language = FuzzyChoice(['eng', 'swa', 'lug'])
    text = factory.Sequence(lambda n: 'Tip text {0}'.format(n))
    tip = factory.SubFactory(TipFactory)


class TipSeriesSubscriptionFactory(DjangoModelFactory):

    class Meta:
        model = models.TipSeriesSubscription

    customer = factory.SubFactory('customers.tests.factories.CustomerFactory')
    series = factory.SubFactory(TipSeriesFactory)
    start = factory.LazyFunction(timezone.now)


class TipSentFactory(DjangoModelFactory):

    class Meta:
        model = models.TipSent

    tip = factory.SubFactory(TipFactory)
    subscription = factory.SubFactory(TipSeriesSubscriptionFactory)


class TipSeasonFactory(DjangoModelFactory):

    class Meta:
        model = models.TipSeason

    commodity = factory.SubFactory('agri.tests.factories.CommodityFactory')
    start_date = factory.LazyFunction(timezone.localdate)
