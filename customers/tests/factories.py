from datetime import date, datetime

import factory
import factory.fuzzy
from factory.django import DjangoModelFactory

from django.utils import timezone

from agri.tests.factories import AgriculturalRegionFactory
from core.constants import FARM_SIZES, LANGUAGES, SEX
from core.constants import PHONE_TYPES
from markets.models import Market, MarketSubscription
from markets.tests.factories import MarketSubscriptionFactory
from tips.models import TipSeries, TipSeriesSubscription
from tips.tests.factories import TipSeriesSubscriptionFactory
from world.models import Border
from subscriptions.models import Subscription, SubscriptionAllowance, SubscriptionType

from customers.models import Customer, CustomerPhone, CustomerCategory


class CustomerCategoryFactory(DjangoModelFactory):
    class Meta:
        model = CustomerCategory
        django_get_or_create = ('name',)

    name = factory.Sequence(lambda n: 'category_%d' % n)


class CustomerFactory(DjangoModelFactory):
    class Meta:
        model = Customer

    name = factory.Sequence(lambda n: 'customer_%d' % n)
    sex = factory.Iterator([SEX.MALE, SEX.FEMALE])
    phones = factory.RelatedFactoryList('customers.tests.factories.CustomerPhoneFactory',
                                        factory_related_name='customer', size=1)

    agricultural_region = factory.SubFactory(AgriculturalRegionFactory)

    border0 = factory.LazyAttribute(lambda o: Border.objects.get(country='Kenya', level=0))
    border1 = factory.LazyAttribute(lambda o: Border.objects.get(country='Kenya', level=1, name='Nairobi'))
    border2 = factory.LazyAttribute(lambda o: Border.objects.get(country='Kenya', level=2, name='Kibra'))
    border3 = factory.LazyAttribute(lambda o: Border.objects.get(country='Kenya', level=3, name='Makina'))

    village = 'test_ville'

    # subscriptions = factory.RelatedFactoryList(
    #     'customers.tests.factories.PremiumSubscriptionFactory',
    #     factory_related_name='customer',
    #     size=1,
    # )

    @factory.post_generation
    def add_phones(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            for p in extracted:
                if isinstance(p, str):
                    p_obj = CustomerPhone.objects.create(number=p, customer_id=self.id)
                    self.phones.add(p_obj)
                elif isinstance(p, CustomerPhone):
                    self.phones.add(p)
                else:
                    raise ValueError(f"Expected phone number str or CustomerPhone object, but got {p.__class__}")

    @factory.post_generation
    def add_main_phones(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            for p in extracted:
                if isinstance(p, str):
                    p_obj = CustomerPhone.objects.create(number=p, customer_id=self.id, is_main=True)
                    self.phones.add(p_obj)
                elif isinstance(p, CustomerPhone):
                    self.phones.add(p)
                else:
                    raise ValueError(f"Expected phone number str or CustomerPhone object, but got {p.__class__}")

    @factory.post_generation
    def commodities(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            self.commodities.add(*extracted)

    @factory.post_generation
    def subscriptions(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            self.subscriptions.add(*extracted)

    preferred_language = factory.Iterator(LANGUAGES)
    phone_type = factory.Iterator([PHONE_TYPES.BASICPHONE, PHONE_TYPES.FEATUREPHONE,
                                   PHONE_TYPES.SMARTPHONE])
    farm_size = factory.fuzzy.FuzzyChoice(FARM_SIZES.values)
    notes = factory.Faker('paragraph')
    weather_area = None

    # This pattern (for handling many-to-many relations with a 'through' model
    # allows us to specify automatically populated market subscriptions and
    # override the customer property of the related model.
    market_subscriptions = factory.RelatedFactoryList(
        'markets.tests.factories.MarketSubscriptionFactory',
        factory_related_name='customer',
        size=2,
    )

    @factory.post_generation
    def add_market_subscriptions(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            for subs in extracted:
                if isinstance(subs, Market):
                    new_subs = MarketSubscriptionFactory(
                        customer=self,
                        market=subs,
                        backup=None,
                    )
                    self.market_subscriptions.add(new_subs)
                elif isinstance(subs, MarketSubscription):
                    subs.customer = self
                    subs.save(update_fields=['customer_id'])
                    self.market_subscriptions.add(subs)
                else:
                    raise ValueError(f"Expected a Market or MarketSubscription, got {type(extracted)}")

    # This pattern (for handling many-to-many relations with a 'through' model
    # allows us to specify automatically populated market subscriptions and
    # override the customer property of the related model.
    tip_subscriptions = factory.RelatedFactoryList(
        'tips.tests.factories.TipSeriesSubscriptionFactory',
        factory_related_name='customer',
        size=2,
    )

    @factory.post_generation
    def add_tip_subscriptions(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            for subs in extracted:
                if isinstance(subs, TipSeries):
                    new_subs = TipSeriesSubscriptionFactory(
                        customer=self,
                        series=subs,
                        start=factory.fuzzy.FuzzyDateTime(timezone.make_aware(datetime(2015, 1, 1))).fuzz(),
                        ended=False,
                    )
                    self.tip_subscriptions.add(new_subs)
                elif isinstance(subs, TipSeriesSubscription):
                    subs.customer = self
                    subs.save(update_fields=['customer_id'])
                    self.tip_subscriptions.add(subs)
                else:
                    raise ValueError(f"Expected a TipSeries or TipSeriesSubscription, got {type(extracted)}")

    @factory.post_generation
    def categories(self, create, extracted, **kwargs):
        # Note that when called (post_generation), the customer object has been
        # created and the "self" passed in is the customer object, not the factory.
        if not create:
            return

        if extracted:
            self.categories.add(*extracted)

    is_registered = True
    # Generate a random date between the approximate date of the platform's creation and now
    date_registered = factory.LazyAttribute(
        lambda o: factory.fuzzy.FuzzyDate(date(2015, 1, 1)).fuzz()
        if o.is_registered else None)

    has_requested_stop = False
    join_method = 'factory'

    location = '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}'

    class Params:
        unregistered = factory.Trait(
            name='',
            is_registered=False,
            date_registered=None,
            has_no_markets=True,
            has_no_subscriptions=True,
            has_no_tips=True,
            has_no_location=True,
        )

        stopped = factory.Trait(
            is_registered=True,
            has_requested_stop=True,
            stop_method='factory',
            stop_date=timezone.now().date(),
        )

        has_no_markets = factory.Trait(
            market_subscriptions=None,
        )

        has_no_tips = factory.Trait(
            tip_subscriptions=None,
        )

        has_no_subscriptions = factory.Trait(
            subscriptions=None,
        )

        has_no_location = factory.Trait(
            border0=None,
            border1=None,
            border2=None,
            border3=None
        )

        # Incompatible with has_no_markets, as this will create two markets, regardless
        has_no_backup_markets = factory.Trait(
            market_subscriptions=factory.RelatedFactoryList(
                'markets.tests.factories.MarketSubscriptionFactory',
                factory_related_name='customer',
                backup=None,
                size=2,
            ),
        )

        # Use 'has_no_phones=True' for a customer without a phone
        has_no_phones = factory.Trait(
            phones=None,
        )

        # Use 'blank=True' for a relatively quick batch creation of customers
        blank = factory.Trait(
            agricultural_region=None,
            border1=None,
            has_no_markets=True,
            has_no_subscriptions=True,
            has_no_tips=True,
        )


class PremiumCustomerFactory(CustomerFactory):
    subscriptions = factory.RelatedFactoryList(
        'customers.tests.factories.PremiumSubscriptionFactory',
        factory_related_name='customer',
        size=1,
    )


class CustomerPhoneFactory(DjangoModelFactory):
    """
    A sub-factory for CustomerFactory only. Do not instantiate directly.
    """
    class Meta:
        model = CustomerPhone

    number = factory.Sequence(lambda n: '+254 702 1%05d' % n)
    is_main = True
    # customer = factory.RelatedFactory(CustomerFactory, 'phones')


class SubscriptionTypeFactory(DjangoModelFactory):
    class Meta:
        model = SubscriptionType

    name = factory.Sequence(lambda n: 'subscription_type_%d' % n)

    @factory.post_generation
    def allowances(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            self.allowances.add(*extracted)


class PremiumSubscriptionTypeFactory(SubscriptionTypeFactory):
    name = 'Premium'
    is_premium = True

    class Meta:
        # Don't create duplicate Premium SubscriptionType objects in the db
        django_get_or_create = ('name',)


class SubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = Subscription

    customer = factory.SubFactory(CustomerFactory)
    type = factory.SubFactory(SubscriptionTypeFactory)


class PremiumSubscriptionFactory(SubscriptionFactory):
    type = factory.SubFactory(PremiumSubscriptionTypeFactory)


class SubscriptionAllowanceFactory(DjangoModelFactory):

    class Meta:
        model = SubscriptionAllowance

    code = factory.Sequence(lambda n: 'subscription_allowance_%d' % n)
    allowance = 2
    type = factory.SubFactory(SubscriptionTypeFactory)
