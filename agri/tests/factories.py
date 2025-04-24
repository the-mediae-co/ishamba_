import factory
from factory.django import DjangoModelFactory

from ..models import AgriTipSMS, Commodity, Region


class CommodityFactory(DjangoModelFactory):
    class Meta:
        model = Commodity
        django_get_or_create = ('name',)

    name = factory.LazyAttributeSequence(
        lambda o, n: '%s_%d' % (o.commodity_type, n))
    short_name = factory.LazyAttribute(lambda o: o.name)
    commodity_type = factory.Iterator([Commodity.CROP, Commodity.LIVESTOCK])
    epoch_description = ''
    variant_of = None
    fallback_commodity = None
    gets_market_prices = factory.LazyAttribute(
        lambda o: o.commodity_type == Commodity.CROP)
    season_length_days = None

    class Params:
        event_based_livestock = factory.Trait(
            commodity_type=Commodity.LIVESTOCK,
            epoch_description='populated',
            fallback_commodity=factory.SubFactory(
                'agri.tests.factories.CommodityFactory')
        )
        seasonal_livestock = factory.Trait(
            commodity_type=Commodity.LIVESTOCK
        )
        crop = factory.Trait(
            commodity_type=Commodity.CROP,
            fallback_commodity=None
        )


class AgriculturalRegionFactory(DjangoModelFactory):
    class Meta:
        model = Region
        django_get_or_create = ('name', )

    name = factory.Sequence(lambda n: 'region_%d' % n)


class AgriTipSMSFactory(DjangoModelFactory):
    class Meta:
        model = AgriTipSMS

    commodity = factory.SubFactory(CommodityFactory)
    region = factory.SubFactory(AgriculturalRegionFactory)
    number = factory.Sequence(lambda n: n)
    text = 'How vainly men themselves amaze\nTo win the palm, the oak, or bays'
