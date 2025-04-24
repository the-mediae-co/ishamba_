import datetime
from copy import copy
from random import randint
from unittest import skip
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import formats, timezone

from django_tenants.test.client import TenantClient as Client

from callcenters.models import CallCenterOperator
import customers.tests.test_all
from agri.models.base import Commodity
from agri.tests.factories import AgriculturalRegionFactory, CommodityFactory
from callcenters.models import CallCenter
from core.constants import SEX
from core.test.cases import TestCase
from customers.constants import JOIN_METHODS, STOP_METHODS
from gateways.africastalking.testing import activate_success_response
from markets.models import Market, MarketSubscription
from markets.tests.factories import MarketFactory, MarketSubscriptionFactory
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS, SMSRecipient
from sms.tests.factories import OutgoingSMSFactory
from tips.models import TipSeries, TipSeriesSubscription
from tips.tests.factories import TipSeriesFactory
from world.models import Border

from ..forms import MarketSubscriptionForm
from ..models import (CommoditySubscription, CropHistory, Customer,
                      CustomerPhone)
from .factories import (CustomerFactory, CustomerPhoneFactory,
                        SubscriptionAllowanceFactory, SubscriptionFactory,
                        SubscriptionTypeFactory)
from .utils import CreateCustomersWithPremiumMixin

# TODO subscription test ideas:
# - tests for querying currently active subscriptions
# - have an aggregation on a subscription stream, (or even denormalise) max and
#   min week values ,for the fallback subscription handling

CUSTOMER_ATTRS = {
    'name': 'Mr John Doe',
    'village': 'somewhere',
}

COMMODITIES = [
    'maize',
    'beans',
    'carrots',
    'horses',
]

VARIANT_COMMODITIES = [
    ('soft maize', 'maize'),
    ('dark maize', 'maize'),
]

MARKETS = [
    {'name': 'Busia', 'short_name': 'bus', 'is_main_market': False},
    {'name': 'Bungoma', 'short_name': 'bun', 'is_main_market': False},
    {'name': 'Embu', 'short_name': 'emb', 'is_main_market': False},
    {'name': 'Nairobi', 'short_name': 'nai', 'is_main_market': True},
    {'name': 'Nakuru', 'short_name': 'nak', 'is_main_market': True},
    {'name': 'Mombasa', 'short_name': 'mom', 'is_main_market': True},
]

USER_ATTRS = {
    'username': 'test_user',
    'password': '1'
}


def Border1Factory(varied=False):
    if varied:
        # Murang'a causes problems for self.assertContains, so exclude it
        return Border.kenya_counties.exclude(name__contains='Murang\'a').order_by('?').first()
    else:
        return Border.objects.get(country='Kenya', level=1, name='Nairobi')


class SubscriptionModelTests(TestCase):

    def setUp(self):
        super().setUp()
        # do this once per class, as these are read-only objects for the
        # purposes of these tests
        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )
        for variant, original in VARIANT_COMMODITIES:
            Commodity.objects.create(
                name=variant,
                short_name=variant[:14],
                variant_of=Commodity.objects.get(name=original)
            )

        kenya = Border.objects.get(name='Kenya', level=0)

        self.markets = {}
        for m in MARKETS:
            defaults = {'location': kenya.border.point_on_surface}
            obj, __ = Market.objects.get_or_create(defaults=defaults, **m)
            self.markets[m['short_name']] = obj

        self.customer = CustomerFactory(has_no_phones=True)
        phone = CustomerPhoneFactory(number='+25420882270', is_main=True, customer=self.customer)
        self.sub_type = SubscriptionTypeFactory()
        SubscriptionAllowanceFactory(code='prices', type=self.sub_type)
        SubscriptionAllowanceFactory(code='markets', type=self.sub_type)
        SubscriptionAllowanceFactory(code='tips', type=self.sub_type)
        SubscriptionFactory(customer=self.customer, type=self.sub_type)

        self.msf = MarketSubscriptionForm(
            {
                'customer': self.customer.pk,
            }
        )

    def tearDown(self):
        Market.objects.all().delete()
        Commodity.objects.all().delete()

    def test_we_can_add_market_subscriptions(self):
        CustomerFactory()
        try:
            MarketSubscription.objects.create(customer=self.customer,
                                              market=list(self.markets.values())[0])
        except Exception:
            self.fail("Adding a commodity subscription raised an error unexpectedly")

    @skip("CommoditySubscription is deprecated")
    def test_cant_add_a_market_price_subscription_when_gets_market_prices_false(self):
        customer = CustomerFactory()
        SubscriptionFactory(customer=customer, type=self.sub_type)

        self.maize.gets_market_prices = False
        self.maize.save()
        expected_msg = ("maize doesn't receive market prices but 'Send market "
                        "prices' was checked.")
        with self.assertRaisesMessage(ValidationError, expected_msg):
            cs = CommoditySubscription(subscriber=customer,
                                       commodity=self.maize,
                                       send_market_prices=True)
            cs.clean()

    @skip("CommoditySubscription is deprecated")
    def test_can_add_market_prices_subscription_when_gets_market_prices_true(self):
        customer = CustomerFactory()
        SubscriptionFactory(customer=customer, type=self.sub_type)

        # TODO: remove once test case refactored to use factory boy
        self.maize.gets_market_prices = True
        self.maize.save()

        try:
            cs = CommoditySubscription(subscriber=customer,
                                       commodity=self.maize,
                                       send_market_prices=True,
                                       send_agri_tips=False)
            cs.clean()
        except Exception:
            self.fail(
                "Failed to create market prices subscription "
                "despite gets_market_prices == True")

    @skip("CommoditySubscription is deprecated")
    def test_form_choices_include_commodities_with_both_prices_and_variants(self):
        self.maize.gets_market_prices = True
        self.maize.save()
        self.assertEqual(self.maize.variants.count(), 2)
        maize_choice = (self.maize.pk, self.maize.name, {'data-prices': 'true'})
        self.assertIn(maize_choice, self.msf.fields['commodity'].choices)
        self.msf.data['commodity'] = self.maize.pk
        try:
            self.msf.is_valid()
        except Commodity.MultipleObjectsReturned:
            self.fail('Cleaning MarketSubscriptionForm raised MultipleObjectsReturned unexpectedly')

    @skip("CommoditySubscription is deprecated")
    def test_form_choices_include_commodities_with_prices_but_no_variants(self):
        self.beans.gets_market_prices = True
        self.beans.save()
        self.assertEqual(self.beans.variants.count(), 0)
        beans_choice = (self.beans.pk, self.beans.name, {'data-prices': 'true'})
        self.assertIn(beans_choice, self.msf.fields['commodity'].choices)
        self.msf.data['commodity'] = self.beans.pk
        try:
            self.msf.is_valid()
        except Commodity.MultipleObjectsReturned:
            self.fail('Cleaning MarketSubscriptionForm raised MultipleObjectsReturned unexpectedly')

    @skip("CommoditySubscription is deprecated")
    def test_form_choices_do_not_include_commodities_without_prices(self):
        self.assertFalse(self.beans.gets_market_prices)
        self.assertEqual(self.beans.variants.count(), 0)
        beans_choice = (self.beans.pk, self.beans.name, {})
        self.assertNotIn(beans_choice, self.msf.fields['commodity'].choices)

    def test_cannot_exceed_the_tip_subscriptions(self):
        tipseries = TipSeriesFactory.create_batch(2)

        for ts in tipseries:
            TipSeriesSubscription.objects.create(
                customer=self.customer, series=ts, start=timezone.now(), ended=False
            )

        expected = "You can only set 2 tip series subscriptions for this customer"
        with self.assertRaisesRegex(ValidationError, expected):
            sub = TipSeriesSubscription(
                customer=self.customer, series=TipSeriesFactory(), start=timezone.now(), ended=False
            )
            sub.full_clean()

    def test_we_cannot_exceed_the_maximum_market_subscriptions(self):
        MarketSubscription.objects.create(
            customer=self.customer, market=self.markets["bus"], backup=self.markets["nak"]
        )

        MarketSubscription.objects.create(
            customer=self.customer, market=self.markets["bun"], backup=self.markets["nai"]
        )

        expected = "You can only set 2 market subscriptions for this customer"
        with self.assertRaisesRegex(ValidationError, expected):
            sub = MarketSubscription(
                customer=self.customer,
                market=self.markets["emb"],
                backup=self.markets["mom"],
            )
            sub.full_clean()


class CustomerQuerySetAndMethodTests(CreateCustomersWithPremiumMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.create_customers()

    def test_can_access_call_centre(self):
        self.assertTrue(Customer.objects.can_access_call_centre().exists())
        for customer in Customer.objects.can_access_call_centre():
            self.assertTrue(customer.can_access_call_centre)

    def test_should_receive_messages(self):
        self.assertTrue(Customer.objects.should_receive_messages().exists())
        for customer in Customer.objects.should_receive_messages():
            self.assertTrue(customer.should_receive_messages)

    def test_registration_date_is_written(self):
        new_customer = Customer.objects.first()
        self.assertEqual(new_customer.is_registered, False)
        self.assertEqual(new_customer.date_registered, None)
        self.assertEqual(new_customer._original_is_registered, False)
        new_customer.is_registered = True
        new_customer.save()
        self.assertEqual(new_customer.date_registered, timezone.now().date())
        # reload from the db
        new_customer = Customer.objects.get(id=new_customer.id)
        self.assertEqual(new_customer.is_registered, True)
        self.assertEqual(new_customer.date_registered, timezone.now().date())
        self.assertEqual(new_customer._original_is_registered, True)

    def test_registration_date_is_not_overwritten(self):
        active_customer = Customer.objects.filter(is_registered=True).first()
        original_date = datetime.date(2014, 5, 1)
        active_customer.date_registered = original_date
        active_customer.save()

        # reload from the db
        active_customer = Customer.objects.get(id=active_customer.id)
        self.assertEqual(active_customer.is_registered, True)
        self.assertEqual(active_customer.date_registered, original_date)
        self.assertEqual(active_customer._original_is_registered, True)

        # deregister the customer, for whatever reason
        active_customer.is_registered = False
        active_customer.save()

        # reload from the db, and reregister
        active_customer = Customer.objects.get(id=active_customer.id)
        self.assertEqual(active_customer.is_registered, False)
        self.assertEqual(active_customer.date_registered, original_date)
        self.assertEqual(active_customer._original_is_registered, False)

        active_customer.is_registered = True
        active_customer.save()

        # reload and check registration date is stil original
        active_customer = Customer.objects.get(id=active_customer.id)
        self.assertEqual(active_customer.is_registered, True)
        self.assertEqual(active_customer.date_registered, original_date)
        self.assertEqual(active_customer._original_is_registered, True)

    def test_count_usage_allowances_subscribed(self):
        expected_limits = {
            'markets': 1,
            'tips': 10,
            'prices': 5,
        }
        customer = CustomerFactory()
        sub_type = SubscriptionTypeFactory()
        SubscriptionAllowanceFactory(code="markets", type=sub_type, allowance=1)
        SubscriptionAllowanceFactory(code="tips", type=sub_type, allowance=10)
        SubscriptionAllowanceFactory(code="prices", type=sub_type, allowance=5)

        SubscriptionFactory(customer=customer, type=sub_type)

        allowances = customer.subscriptions.count_usage_allowances()
        self.assertEqual(allowances, expected_limits)

    def test_count_usage_allowances_with_two_subscriptions_of_same_type(self):
        expected_limits = {
            'markets': 2,
            'tips': 2,
            'prices': 2,
        }
        customer = CustomerFactory()
        sub_type = SubscriptionTypeFactory()
        SubscriptionAllowanceFactory(code="markets", type=sub_type, allowance=1)
        SubscriptionAllowanceFactory(code="tips", type=sub_type, allowance=1)
        SubscriptionAllowanceFactory(code="prices", type=sub_type, allowance=1)

        SubscriptionFactory(customer=customer, type=sub_type)
        SubscriptionFactory(customer=customer, type=sub_type)

        allowances = customer.subscriptions.count_usage_allowances()
        self.assertEqual(allowances, expected_limits)

    def test_check_when_no_allowances_added(self):
        expected_limits = {
            'markets': 0,
            'tips': 0,
            'prices': 0,
        }
        customer = CustomerFactory()
        allowances = customer.subscriptions.count_usage_allowances()
        self.assertEqual(allowances, expected_limits)

    def test_get_single_usage_allowance(self):
        expected_value = 5
        customer = CustomerFactory()
        sub_type = SubscriptionTypeFactory()
        SubscriptionAllowanceFactory(code="markets", type=sub_type, allowance=5)

        SubscriptionFactory(customer=customer, type=sub_type)
        self.assertEqual(customer.subscriptions.get_usage_allowance('markets'),
                         expected_value)

    def test_get_single_usage_allowance_with_multiple_subscriptions(self):
        expected_value = 10
        customer = CustomerFactory()
        sub_type = SubscriptionTypeFactory()
        SubscriptionAllowanceFactory(code="markets", type=sub_type, allowance=5)

        SubscriptionFactory(customer=customer, type=sub_type)
        SubscriptionFactory(customer=customer, type=sub_type)
        self.assertEqual(customer.subscriptions.get_usage_allowance('markets'),
                         expected_value)

    def test_get_missing_usage_allowance(self):
        customer = CustomerFactory()
        out = customer.subscriptions.get_usage_allowance('my_limit')
        self.assertEqual(out, 0)


class CustomerCanReceiveMarketPricesQuerySetMethodTests(TestCase):
    """ More detailed tests of .can_receive_market_prices() and
    .cannot_receive_market_prices()
    """

    def setUp(self):
        super().setUp()
        self.can = (Customer.objects.should_receive_messages()
                                    .can_receive_market_prices())
        self.cannot = (Customer.objects.should_receive_messages()
                                       .cannot_receive_market_prices())

    def test_customer_with_no_commodities(self):
        customer = CustomerFactory(
            commodities=None,
            has_no_tips=True,  # TipSeriesFactory creates commodities as well
        )
        self.assertEqual(0, customer.commodities.count())
        self.assertEqual(2, customer.market_subscriptions.count())  # Factory produces 2 market subscriptions by default
        # CANNOT!
        self.assertEqual(self.can.count(), 0)
        self.assertEqual(self.cannot.count(), 2)

    def test_customer_with_no_markets(self):
        customer = CustomerFactory(
            has_no_markets=True,
            has_no_tips=True,
        )
        self.assertEqual(0, customer.market_subscriptions.count())
        # CANNOT!
        self.assertEqual(self.can.count(), 0)
        self.assertEqual(self.cannot.count(), 1)

    def test_customer_with_one_commodity_and_market_sends(self):
        market = MarketFactory()
        maize = CommodityFactory(name='Maize', crop=True)
        customer = CustomerFactory(
            blank=True,  # We don't want the CustomerFactory to create commodities and markets
            commodities=[maize],     # Add the ones we want
            add_market_subscriptions=[market],
        )
        self.assertEqual(1, customer.market_subscriptions.count())
        self.assertEqual(1, customer.commodities.count())
        # CAN!
        self.assertEqual(self.can.count(), 1)
        self.assertEqual(self.cannot.count(), 0)

    def test_customer_with_one_commodity_but_no_market_cannot_send(self):
        maize = CommodityFactory(name='Maize', crop=True)
        customer = CustomerFactory(
            commodities=[maize],  # Add one commodity
            has_no_markets=True,  # ...and no markets
            has_no_tips=True)     # ...and no tips (they create commodities as well)
        self.assertEqual(0, customer.market_subscriptions.count())
        self.assertEqual(1, customer.commodities.count())
        # CANNOT!
        self.assertEqual(self.can.count(), 0)
        self.assertEqual(self.cannot.count(), 1)


class CustomerCreateViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')

        self.client = Client(self.tenant)
        self.client.login(username='foo', password='foo')

        Border.objects.get(name='Kenya', level=0)

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.north = AgriculturalRegionFactory(name='The North')
        self.south = AgriculturalRegionFactory(name='The South')

        self.commodity = Commodity.objects.all().first()

        self.nairobi_county = Border1Factory()

    @activate_success_response
    def test_create_valid_customer_sends_welcome_sms(self):
        def generate_unique_phone():
            return f'+254720{randint(100000, 999999)}'

        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': generate_unique_phone(),
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'border1_id': self.nairobi_county.id,
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(0, OutgoingSMS.objects.count(), msg="No SMS objects expected before customer creation")
        self.assertEqual(0, SMSRecipient.objects.count(), msg="No SMS objects expected before customer creation")

        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )

        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count(), msg="Welcome message not sent")

        # Check the number of SMS recipients, depending on the number of paginated messages
        self.assertGreaterEqual(SMSRecipient.objects.count(), 1, msg="SMS recipients not created")
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])

        phone = CustomerPhone.objects.get(number=data['phones'])
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)

    @activate_success_response
    def test_create_valid_customer_is_registered_sends_welcome_sms_swahili(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'border1': self.nairobi_county.pk,  # Causes the form to be invalid?
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'swa',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())  # The welcome message paginates to 2 messages.
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])
        phone = CustomerPhone.objects.get(number=data['phones'])
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)

    @activate_success_response
    def test_create_valid_customer_not_is_registered_sends_welcome_sms(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'is_registered': False,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())  # The welcome message paginates to 2 messages.
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])
        phone = CustomerPhone.objects.get(number=data['phones'])
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)

    @activate_success_response
    def test_create_valid_customer_unknown_registered_sends_welcome_sms(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())  # The welcome message paginates to 2 messages.
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])
        number = data['phones'].split()[0].strip()
        phone = CustomerPhone.objects.get(number=number)
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)

    @activate_success_response
    def test_create_valid_492_customer_sends_welcome_sms(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456, +4924662153943453',
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())  # The welcome message paginates to 1 message.
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])
        number = data['phones'].split()[0].strip()
        phone = CustomerPhone.objects.get(number=number)
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)


    @activate_success_response
    def test_create_valid_intl_customer_sends_welcome_sms(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+18156750504',
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())  # The welcome message paginates to 1 message.
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])
        number = data['phones'].split(',')[0].strip()
        phone = CustomerPhone.objects.get(number=number)
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)

    @activate_success_response
    def test_create_valid_dual_country_customer_sends_welcome_sms_to_main_phone(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456,+256720123456,+18156750504',
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        resp = self.client.post(
            reverse('customers:customer_create'),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())  # The welcome message paginates to 1 message.
        number = data['phones'].split(',')[0].strip()
        self.assertEqual(number, SMSRecipient.objects.first().extra['number'])
        self.assertEqual(['Welcome SMS Sent'], [str(m) for m in resp.context['messages']])
        phone = CustomerPhone.objects.get(number=number)
        c = Customer.objects.get(phones=phone)
        self.assertEqual(JOIN_METHODS.STAFF, c.join_method)


class CustomerUpdateTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(**CUSTOMER_ATTRS)
        phone = CustomerPhone.objects.create(number='+254720123456', is_main=True, customer=self.customer)
        self.client = Client(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

        kenya = Border.objects.get(name='Kenya', level=0)

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.north = AgriculturalRegionFactory(name='The North')
        self.south = AgriculturalRegionFactory(name='The South')

        self.commodity = Commodity.objects.all().first()

        self.nairobi_county = Border1Factory()

    def test_customer_exists(self):
        self.assertTrue(self.customer)
        self.assertNotEqual(JOIN_METHODS.STAFF, self.customer.join_method)

    @activate_success_response
    def test_customer_update_works(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'county': self.nairobi_county.pk,
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))

    @activate_success_response
    def test_customer_update_multiple_phones_works(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456,+254720123457, +254720123458',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'county': self.nairobi_county.pk,
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(1, self.customer.phones.count())

        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))
        self.assertEqual(3, self.customer.phones.count())
        self.assertEqual('+254720123456', self.customer.main_phone)
        numbers = self.customer.phones.values_list('number', flat=True)
        for number in numbers:
            self.assertTrue(number in data['phones'])

    @activate_success_response
    def test_customer_update_duplicate_phones_works(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456,+254720123456',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'county': self.nairobi_county.pk,
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(1, self.customer.phones.count())

        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))
        # The duplicates should resolve to one phone number stored
        self.assertEqual(1, self.customer.phones.count())
        self.assertEqual('+254720123456', self.customer.main_phone)

    @activate_success_response
    def test_customer_update_invalid_phones_fails(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456,+2',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'county': self.nairobi_county.pk,
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(1, self.customer.phones.count())

        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertContains(resp, '+2 is not a valid phone number')
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))
        # The duplicates should resolve to one phone number stored
        self.assertEqual(1, self.customer.phones.count())
        self.assertEqual('+254720123456', self.customer.main_phone)

    @activate_success_response
    def test_customer_update_no_phones_fails(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'county': self.nairobi_county.pk,
            'is_registered': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(1, self.customer.phones.count())

        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        self.assertContains(resp, 'This field is required')
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))
        # The customer should retain their initial number
        self.assertEqual(1, self.customer.phones.count())

    @activate_success_response
    def test_492_customer_update_works(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': f"+4924662153943453,+254720123456",
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))

    @activate_success_response
    def test_intl_customer_update_works(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+18156750504',
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))

    def test_customer_set_stop_flag_sets_stop_method(self):
        data = copy(CUSTOMER_ATTRS)
        data.update({
            'phones': '+254720123456',
            'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
            'county': self.nairobi_county.pk,
            'is_registered': True,
            'has_requested_stop': True,
            'commodities': self.commodity.pk,
            'agricultural_region': self.north.pk,
            'preferred_language': 'eng',
            'market_subscriptions-TOTAL_FORMS': '2',
            'market_subscriptions-INITIAL_FORMS': '0',
            'market_subscriptions-MIN_NUM_FORMS': '0',
            'market_subscriptions-MAX_NUM_FORMS': '1000',
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
            'answers-MIN_NUM_FORMS': '0',
            'answers-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        resp = self.client.post(
            reverse('customers:customer_update', kwargs={'pk': self.customer.pk}),
            data=data,
            follow=True
        )
        self.assertEqual(200, resp.status_code)
        # We no longer send a welcome SMS on customer update.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        self.assertEqual(0, len(resp.context['messages']))

        phone = CustomerPhone.objects.get(number=data['phones'])
        customer = Customer.objects.get(phones=phone)
        self.assertEqual(STOP_METHODS.STAFF, customer.stop_method)
        self.assertEqual(timezone.now().date(), customer.stop_date)


class CustomerListViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.call_center = CallCenter.objects.get(border=Border.objects.get(country='Kenya', level=0))
        self.call_center_operator = CallCenterOperator.objects.create(operator=self.operator, active=True, call_center=self.call_center)
        self.client.login(username='foo', password='foo')

        kenya = Border.objects.get(name='Kenya', level=0)

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.north = AgriculturalRegionFactory(name='The North')
        self.south = AgriculturalRegionFactory(name='The South')

        self.commodity = Commodity.objects.all().first()

        self.nairobi_county = Border1Factory()
        self.second_county = Border1Factory(varied=True)
        while self.second_county.name == self.nairobi_county.name:
            self.second_county = Border1Factory(varied=True)

        self.test_customers = [
            CustomerFactory(is_registered=True, name="IsRegistered", sex=SEX.FEMALE),
            CustomerFactory(is_registered=True, name="Is2Registered2", sex=SEX.MALE, categories=[1]),
            CustomerFactory(is_registered=False, name="NotRegistered", sex=''),
            CustomerFactory(has_requested_stop=True, name="RequestedStop"),
            CustomerFactory(agricultural_region=self.south, border1=self.nairobi_county, name="Nairobi"),
            CustomerFactory(agricultural_region=self.north, border1=self.second_county, name="Meru"),
            CustomerFactory(name="DigiphoneJoe", digifarm_farmer_id=49, has_no_phones=True),
            CustomerFactory(name="NoWard", border3=None),
            CustomerFactory(name="UssdJoin", join_method='ussd'),
            CustomerFactory(name="SmsStop", stop_method='sms'),
            CustomerFactory(name="LastEdited", last_editor_id=self.operator.id),
        ]
        phone = CustomerPhoneFactory(number='+4929951568174106', is_main=False, customer=self.test_customers[6])
        pass

    def test_customer_factory(self):
        self.assertTrue(self.test_customers[0].is_registered)
        self.assertEqual(Customer.objects.count(), len(self.test_customers))

    def test_customer_list_renders_correct_template(self):
        response = self.client.get(reverse('customers:customer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/customer_list.html'], response.template_name)

    def test_customer_list_renders_all_customers(self):
        response = self.client.get(reverse('customers:customer_list'))
        self.assertEqual(response.status_code, 200)
        for customer in self.test_customers:
            self.assertContains(response, customer.name)

    def test_customer_list_renders_sex(self):
        response = self.client.get(reverse('customers:customer_list'))
        self.assertEqual(response.status_code, 200)
        for customer in self.test_customers:
            self.assertContains(response, customer.sex)

    def test_customer_list_renders_county(self):
        response = self.client.get(reverse('customers:customer_list'))
        self.assertEqual(response.status_code, 200)
        for customer in self.test_customers:
            self.assertContains(response, customer.border1)

    def test_customer_list_does_not_render_phone(self):
        response = self.client.get(reverse('customers:customer_list'))
        self.assertEqual(response.status_code, 200)
        for customer in self.test_customers:
            if customer.main_phone:
                self.assertNotContains(response, customer.main_phone)

    def test_customer_list_renders_region(self):
        response = self.client.get(reverse('customers:customer_list'))
        self.assertEqual(response.status_code, 200)
        for customer in self.test_customers:
            self.assertContains(response, customer.agricultural_region)

    def test_customer_list_pagination(self):
        from customers.views.customer import CustomerListView
        rows_per_page = CustomerListView.paginate_by
        num_pages = 5
        for i in range(num_pages*rows_per_page):
            CustomerFactory(is_registered=True)
        self.assertEqual(num_pages*rows_per_page+len(self.test_customers), Customer.objects.count())
        for page in range(num_pages):
            response = self.client.get(reverse('customers:customer_list') + f'?page={page+1}')
            self.assertEqual(response.status_code, 200)

    def test_customer_phone_filter_works(self):
        response = self.client.get(reverse('customers:customer_list'),
                                   {"phone": "254"}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Ensure all Kenya phone customers are displayed
        for c in self.test_customers:
            if c.phones.filter(number__startswith='+254'):
                self.assertContains(response, c.name)

        response = self.client.get(reverse('customers:customer_list'),
                                    {"phone": "+49"}, follow=True)
        self.assertEqual(response.status_code, 200)
        for c in self.test_customers:
            if c.digifarm_farmer_id:
                self.assertContains(response, c.name)  # Ensure the name is displayed
                self.assertNotContains(response, "+492")  # ...but the fake DF number is not

        self.assertContains(response, "DigiphoneJoe")   # Ensure the name is displayed
        self.assertNotContains(response, "174106", 200, "Found a filtered-out customer") # ...but the fake DF number is not

    def test_customer_id_filter_works(self):
        c0 = self.test_customers[0]
        c1 = self.test_customers[1]
        response = self.client.get(reverse('customers:customer_list'),
                                   {"customer_id": c0.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(c0, filtered_customers)
        self.assertNotIn(c1, filtered_customers)

    def test_customer_name_filter_works(self):
        c0 = self.test_customers[0]
        c1 = self.test_customers[1]
        response = self.client.get(reverse('customers:customer_list'),
                                   {"name": c0.name}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(c0, filtered_customers)
        self.assertNotIn(c1, filtered_customers)

    def test_customer_sex_filter_works(self):
        c0 = self.test_customers[0]
        c1 = self.test_customers[1]
        response = self.client.get(reverse('customers:customer_list'),
                                   {"sex": c0.sex}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(c0, filtered_customers)
        self.assertNotIn(c1, filtered_customers)

    def test_customer_border1_filter_works(self):
        c0 = self.test_customers[4]
        c1 = self.test_customers[5]

        # Confirm border1 exists on c1
        self.assertIsNotNone(c1.border1)

        # Filter by border1 ID and check the response
        response = self.client.get(reverse('customers:customer_list'),
                                   {"border1": [c1.border1.id]}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Get filtered customers from the context
        filtered_customers = response.context_data.get('customer_list')

        # Debugging: Print out filtered customers for debugging purposes
        print(filtered_customers)

        # Assert c1 is in the filtered customers
        self.assertIn(c1, filtered_customers)
        self.assertNotIn(c0, filtered_customers)
        self.assertEqual(1, filtered_customers.count())

    def test_customer_category_filter_works(self):
        c0 = self.test_customers[0]
        c1 = self.test_customers[1]

        # Verify that c1 has categories assigned
        print(f"c1 categories: {c1.categories.all()}")  # Check categories for c1
        self.assertTrue(c1.categories.exists())  # Ensure c1 has at least one category

        # Apply category filter and check response
        response = self.client.get(reverse('customers:customer_list'),
                                   {"categories": c1.categories.first().id}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Get filtered customers from the response
        filtered_customers = response.context_data.get('customer_list')

        # Print filtered customers for debugging
        print(filtered_customers)

        # Assert c1 is in the filtered customers and c0 is not
        self.assertIn(c1, filtered_customers)
        self.assertNotIn(c0, filtered_customers)
        self.assertEqual(1, filtered_customers.count())

    def test_customer_complete_location_filter_works(self):
        no_location = self.test_customers[7]
        has_location = self.test_customers[5]

        # Print the location attributes for debugging

        # Apply the complete_location filter for "Yes"
        response = self.client.get(reverse('customers:customer_list'),
                                   {"complete_location": "Yes"}, follow=True)
        self.assertEqual(response.status_code, 200)

        filtered_customers = response.context_data.get('customer_list')
        print(filtered_customers)  # Check which customers are in the filtered list
        self.assertIn(has_location, filtered_customers)
        self.assertNotIn(no_location, filtered_customers)

        # Apply the complete_location filter for "No"
        response = self.client.get(reverse('customers:customer_list'),
                                   {"complete_location": "No"}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(no_location, filtered_customers)
        self.assertNotIn(has_location, filtered_customers)

        # Apply the complete_location filter for "ALL"
        response = self.client.get(reverse('customers:customer_list'),
                                   {"complete_location": "ALL"}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(no_location, filtered_customers)
        self.assertIn(has_location, filtered_customers)

    def test_customer_has_gender_filter_works(self):
        has_gender = self.test_customers[0]
        no_gender = self.test_customers[2]

        # Ensure the gender is set correctly
        has_gender.gender = 'Male'  # Set this to a valid gender
        has_gender.save()

        no_gender.gender = None  # Set this to None or blank
        no_gender.save()

        # Test for "Yes" gender
        response = self.client.get(reverse('customers:customer_list'),
                                   {"has_gender": "Yes"}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(has_gender, filtered_customers)
        self.assertNotIn(no_gender, filtered_customers)

        # Test for "No" gender
        response = self.client.get(reverse('customers:customer_list'),
                                   {"has_gender": "No"}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(no_gender, filtered_customers)
        self.assertNotIn(has_gender, filtered_customers)

        # Test for "ALL" gender
        response = self.client.get(reverse('customers:customer_list'),
                                   {"has_gender": "ALL"}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(no_gender, filtered_customers)
        self.assertIn(has_gender, filtered_customers)

    def test_customer_id_filter_works(self):
        c0 = self.test_customers[0]
        c1 = self.test_customers[1]

        # Ensure c0 has the correct ID
        self.assertIsNotNone(c0.id)  # This should not be None, meaning the customer has been saved properly.

        # Make sure customers are saved
        c0.save()
        c1.save()

        # Now test the filter
        response = self.client.get(reverse('customers:customer_list'),
                                   {"customer_id": c0.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(c0, filtered_customers)  # Ensure c0 is in the filtered list
        self.assertNotIn(c1, filtered_customers)  # Ensure c1 is not in the filtered list

    def test_customer_stop_method_filter_works(self):
        stop_customer = self.test_customers[9]
        non_stop_customer = self.test_customers[8]
        response = self.client.get(reverse('customers:customer_list'),
                                   {"stop_method": "sms"}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(stop_customer, filtered_customers)
        self.assertNotIn(non_stop_customer, filtered_customers)
        self.assertEqual(1, len(filtered_customers))

    def test_customer_last_editor_filter_works(self):
        last_edited_customer = self.test_customers[10]
        non_last_edited_customer = self.test_customers[9]
        response = self.client.get(reverse('customers:customer_list'),
                                   {"last_editor": self.operator.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        filtered_customers = response.context_data.get('customer_list')
        self.assertIn(last_edited_customer, filtered_customers)
        self.assertNotIn(non_last_edited_customer, filtered_customers)
        self.assertEqual(1, len(filtered_customers))


class CustomerDetailViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

        kenya = Border.objects.get(name='Kenya', level=0)

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.north = AgriculturalRegionFactory(name='The North')
        self.south = AgriculturalRegionFactory(name='The South')

        self.commodity = Commodity.objects.all().first()

        self.nairobi_county = Border1Factory()
        self.second_county = Border1Factory(varied=True)

        self.test_customers = [
            CustomerFactory(is_registered=True, name="IsRegistered", sex=SEX.FEMALE),
            CustomerFactory(is_registered=True, name="Is2Registered2", sex=SEX.MALE),
            CustomerFactory(is_registered=False, name="NotRegistered"),
            CustomerFactory(has_requested_stop=True, name="RequestedStop"),
            CustomerFactory(agricultural_region=self.south, border1=self.nairobi_county, name="Nairobi"),
            CustomerFactory(agricultural_region=self.north, border1=self.second_county, name="Meru"),
            CustomerFactory(name="DigiphoneJoe", digifarm_farmer_id=49, has_no_phones=True)
        ]
        phone = CustomerPhoneFactory(number='+4929951568174106', is_main=False, customer=self.test_customers[6])
        pass

        self.outgoing_sms = [
            OutgoingSMSFactory(text='message-text-one',
                               message_type=OUTGOING_SMS_TYPE.INDIVIDUAL),
            OutgoingSMSFactory(text='message-text-two',
                               message_type=OUTGOING_SMS_TYPE.BULK),
            OutgoingSMSFactory(text='message-text-three',
                               sent_by=self.operator,
                               message_type=OUTGOING_SMS_TYPE.INDIVIDUAL),
        ]

        SMSRecipient.objects.create(recipient_id=self.test_customers[0].pk,
                                    message=self.outgoing_sms[0],
                                    page_index=1,
                                    gateway_msg_id="abc123",
                                    extra={
                                        'messageId': "abc123",
                                        'cost': "ksh 0.6",
                                        'page': {
                                            'total': 1,
                                        }
                                    })
        SMSRecipient.objects.create(recipient_id=self.test_customers[2].pk,
                                    message=self.outgoing_sms[2],
                                    page_index=1,
                                    gateway_msg_id="abc123" + str(self.test_customers[2].pk),
                                    extra={
                                        'messageId': "abc123" + str(self.test_customers[2].pk),
                                        'cost': "ksh 0.6",
                                        'page': {
                                            'total': 1,
                                        }
                                    })
        for c in self.test_customers:
            SMSRecipient.objects.create(recipient_id=c.pk,
                                        message=self.outgoing_sms[1],
                                        page_index=1,
                                        gateway_msg_id="def123" + str(c.pk),
                                        extra={
                                            'messageId': "def123" + str(c.pk),
                                            'cost': "ksh 0.6",
                                            'page': {
                                                'total': 1,
                                            }
                                        })

    def test_customer_factory(self):
        self.assertTrue(self.test_customers[0].is_registered)
        self.assertEqual(Customer.objects.count(), len(self.test_customers))

    def test_customer_detail_renders_correct_template(self):
        response = self.client.get(reverse('customers:customer_detail', args=[self.test_customers[0].id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/customer_detail.html'], response.template_name)

    def test_customer_detail_renders_customer_name(self):
        customer = self.test_customers[0]
        response = self.client.get(reverse('customers:customer_detail', args=[customer.id]))
        self.assertContains(response, customer.name)

    def test_customer_detail_renders_customer_sex(self):
        customer = self.test_customers[1]
        response = self.client.get(reverse('customers:customer_detail', args=[customer.id]))
        self.assertContains(response, customer.sex)

    def test_customer_detail_does_not_render_customer_phone(self):
        customer = self.test_customers[2]
        response = self.client.get(reverse('customers:customer_detail', args=[customer.id]))
        self.assertNotContains(response, customer.main_phone.as_international)

    def test_customer_detail_renders_customer_county(self):
        customer = self.test_customers[4]
        response = self.client.get(reverse('customers:customer_detail', args=[customer.id]))
        self.assertContains(response, customer.border1)

    def test_customer_detail_renders_customer_region(self):
        customer = self.test_customers[5]
        response = self.client.get(reverse('customers:customer_detail', args=[customer.id]))
        self.assertContains(response, customer.agricultural_region)

    def test_customer_detail_outgoingsms_filter(self):
        response = self.client.get(reverse('customers:customer_outgoing_sms_history', args=[self.test_customers[0].pk]),
                                   {"message_type": OUTGOING_SMS_TYPE.INDIVIDUAL}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Ensure that the messages are displayed
        self.assertContains(response, OUTGOING_SMS_TYPE.INDIVIDUAL)
        self.assertContains(response, self.outgoing_sms[0].text)
        # Ensure that others are not
        self.assertNotContains(response, self.outgoing_sms[1].text)
        self.assertNotContains(response, self.outgoing_sms[2].text)

        response = self.client.get(reverse('customers:customer_outgoing_sms_history', args=[self.test_customers[1].pk]),
                                   {"message_type": OUTGOING_SMS_TYPE.BULK}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Ensure that the messages are displayed
        self.assertContains(response, OUTGOING_SMS_TYPE.BULK)
        self.assertContains(response, self.outgoing_sms[1].text)
        # Ensure that others are not
        self.assertNotContains(response, self.outgoing_sms[0].text)
        self.assertNotContains(response, self.outgoing_sms[2].text)

        response = self.client.get(reverse('customers:customer_outgoing_sms_history', args=[self.test_customers[2].pk]),
                                   {"sent_by": self.operator.pk}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Ensure that the messages are displayed
        self.assertContains(response, OUTGOING_SMS_TYPE.INDIVIDUAL)
        self.assertContains(response, self.outgoing_sms[2].text)
        # Ensure that others are not
        self.assertNotContains(response, self.outgoing_sms[0].text)
        self.assertNotContains(response, self.outgoing_sms[1].text)


class CropHistoryTestCases(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.commodity = Commodity.objects.first()
        self.customer = CustomerFactory(is_registered=True, name="IsRegistered", sex=SEX.FEMALE)
        self.crop_history = CropHistory.objects.create(
            customer=self.customer,
            commodity=self.commodity,
            date_planted=datetime.date(1984, 1, 1)
        )

    def test_customer_factory(self):
        self.assertTrue(self.customer.is_registered)
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(1, CropHistory.objects.count())

    def test_logged_in_add_crop_history_renders(self):
        response = self.client.get(reverse('customers:customer_crop_history_create', args=[self.customer.pk]),
                                   follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/crophistory_form.html'], response.template_name)

    def test_logged_out_add_crop_history_redirects(self):
        self.client.logout()
        response = self.client.get(reverse('customers:customer_crop_history_create', args=[self.customer.pk]),
                                   follow=True)
        self.assertRedirects(response, f'/accounts/login/?next=/customers/customer/{self.customer.pk}/crop_history/new/',
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_update_crop_history_updates(self):
        response = self.client.post(reverse('customers:customer_crop_history_update', args=[self.crop_history.pk]),
                                    {'date_planted': '2021-01-01',
                                     'customer': self.customer.pk,
                                     'commodity': self.commodity.pk},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/crophistory_list.html'], response.template_name)
        self.crop_history.refresh_from_db()
        self.assertEqual(datetime.date(2021, 1, 1), self.crop_history.date_planted)

    def test_logged_out_update_crop_history_redirects(self):
        self.client.logout()
        response = self.client.post(reverse('customers:customer_crop_history_update', args=[self.crop_history.pk]),
                                    {'date_planted': '2021-01-01',
                                     'customer': self.customer.pk,
                                     'commodity': self.commodity.pk},
                                    follow=True)
        self.assertRedirects(response, f'/accounts/login/?next=/customers/customer/crop_history/{self.crop_history.pk}/update/',
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.crop_history.refresh_from_db()
        self.assertEqual(datetime.date(1984, 1, 1), self.crop_history.date_planted)

    def test_logged_in_get_delete_crop_history_succeeds(self):
        # Starting in django 4, delete must be as a result of a post, not a get
        response = self.client.get(reverse('customers:customer_crop_history_delete', args=[self.crop_history.pk]),
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/crophistory_confirm_delete.html'], response.template_name)
        # Ensure that there are no success messages
        self.assertEqual(0, len(list(response.context.get('messages'))))
        self.assertEqual(1, CropHistory.objects.count())  # Object is not deleted without confirmation

    def test_logged_in_post_delete_crop_history_succeeds(self):
        response = self.client.post(reverse('customers:customer_crop_history_delete', args=[self.crop_history.pk]),
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/crophistory_list.html'], response.template_name)
        # get message from context and check that expected text is there
        message = list(response.context.get('messages'))[0]
        self.assertEqual(message.tags, "success")
        self.assertTrue("deleted successfully" in message.message)
        self.assertEqual(0, CropHistory.objects.count())  # Object is deleted after confirmation

    def test_logged_out_get_delete_crop_history_redirects(self):
        self.client.logout()
        response = self.client.get(reverse('customers:customer_crop_history_delete', args=[self.crop_history.pk]),
                                   follow=True)
        self.assertRedirects(response, f'/accounts/login/?next=/customers/customer/crop_history/{self.crop_history.pk}/delete/',
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.crop_history.refresh_from_db()
        self.assertEqual(datetime.date(1984, 1, 1), self.crop_history.date_planted)

    def test_logged_out_post_delete_crop_history_redirects(self):
        self.client.logout()
        response = self.client.post(reverse('customers:customer_crop_history_delete', args=[self.crop_history.pk]),
                                    follow=True)
        self.assertRedirects(response, f'/accounts/login/?next=/customers/customer/crop_history/{self.crop_history.pk}/delete/',
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.crop_history.refresh_from_db()
        self.assertEqual(datetime.date(1984, 1, 1), self.crop_history.date_planted)

    def test_logged_in_crop_history_displays(self):
        response = self.client.get(reverse('customers:customer_crop_history_list', args=[self.customer.pk]),
                                   follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/crophistory_list.html'], response.template_name)
        self.assertContains(response, self.commodity.name, count=1)
        self.assertContains(response, formats.date_format(self.crop_history.date_planted, use_l10n=True), count=1)

    def test_logged_out_crop_history_redirects(self):
        self.client.logout()
        response = self.client.get(reverse('customers:customer_crop_history_list', args=[self.customer.pk]),
                                   follow=True)
        self.assertRedirects(response, f'/accounts/login/?next=/customers/customer/{self.customer.pk}/crop_history/',
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_post_crop_history_rejects(self):
        response = self.client.post(reverse('customers:customer_crop_history_list', args=[self.customer.pk]),
                                    follow=True)
        self.assertEqual(405, response.status_code)


class CommodityTestCases(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.commodity = Commodity.objects.first()
        self.customer = CustomerFactory(
            blank=True,
            is_registered=True,
            name="IsRegistered",
            sex=SEX.FEMALE,
            commodities=[self.commodity]
        )

    def test_customer_factory(self):
        self.assertTrue(self.customer.is_registered)
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(1, self.customer.commodities.count())

    def test_logged_in_list_commodity_renders(self):
        response = self.client.get(
            reverse("customers:customer_commodity_list", args=[self.customer.pk]),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertIn('customers/commodity_list.html', response.template_name)

    def test_logged_out_list_commodity_redirects(self):
        self.client.logout()
        response = self.client.get(
            reverse("customers:customer_commodity_list", args=[self.customer.pk]),
            follow=True
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.pk}/commodities/",
            status_code=302,
            target_status_code=200,
        )
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_add_commodity_renders(self):
        response = self.client.get(
            reverse('customers:customer_commodity_add', args=[self.customer.pk]),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/commodity_form.html'], response.template_name)

    def test_logged_out_add_commodity_redirects(self):
        self.client.logout()
        response = self.client.get(
            reverse("customers:customer_commodity_add", args=[self.customer.pk]),
            follow=True
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.pk}/commodities/add/",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_get_commodity_remove_rejects(self):
        # Starting in django 4, delete must be as a result of a post, not a get
        response = self.client.get(
            reverse(
                "customers:customer_commodity_remove",
                args=[self.customer.pk, self.customer.commodities.first().pk],
            ),
            follow=True,
        )
        self.assertEqual(405, response.status_code)
        self.assertEqual(1, self.customer.commodities.count())  # Commodity was not removed

    def test_logged_in_post_commodity_remove_succeeds(self):
        response = self.client.post(
            reverse(
                "customers:customer_commodity_remove",
                args=[self.customer.pk, self.commodity.pk],
            ),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.is_rendered)
        self.assertIn('customers/commodity_list.html', response.template_name)
        # get message from context and check that expected text is there
        message = list(response.context.get('messages'))[0]
        self.assertEqual("success", message.tags)
        self.assertTrue("was removed" in message.message)
        self.assertEqual(0, self.customer.commodities.count())  # Object is deleted

    def test_logged_in_post_market_subscribed_commodity_remove_fails(self):
        market_subscription = MarketSubscriptionFactory(
            customer=self.customer,
            commodity=self.commodity
        )

        response = self.client.post(
            reverse(
                "customers:customer_commodity_remove",
                args=[self.customer.pk, self.commodity.pk],
            ),
            follow=False,
        )
        self.assertEqual(302, response.status_code)
        self.assertRedirects(
            response,
            f'/customers/customer/{self.customer.id}/commodities/',
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(1, self.customer.commodities.count())  # Object is NOT deleted

    def test_logged_in_post_tip_subscribed_commodity_remove_fails(self):
        tip_series = TipSeries.objects.create(
            name=self.commodity.name,
            commodity=self.commodity,
            legacy=False,
        )
        tss = TipSeriesSubscription.objects.create(
            customer=self.customer,
            series=tip_series,
            start=timezone.now(),
            ended=False,
        )
        response = self.client.post(
            reverse(
                "customers:customer_commodity_remove",
                args=[self.customer.pk, self.customer.commodities.first().pk],
            ),
            follow=False,
        )
        self.assertEqual(302, response.status_code)
        self.assertRedirects(
            response,
            f'/customers/customer/{self.customer.id}/commodities/',
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(1, self.customer.commodities.count())  # Object is NOT deleted

    def test_logged_out_get_commodity_remove_redirects(self):
        self.client.logout()
        response = self.client.get(
            reverse(
                "customers:customer_commodity_remove",
                args=[self.customer.pk, self.customer.commodities.first().pk],
            ),
            follow=True,
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.id}/commodities/{self.customer.commodities.first().pk}/remove/",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.assertEqual(1, self.customer.commodities.count())

    def test_logged_out_post_commodity_remove_redirects(self):
        self.client.logout()
        response = self.client.post(
            reverse(
                "customers:customer_commodity_remove",
                args=[self.customer.pk, self.customer.commodities.first().pk],
            ),
            follow=True,
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.id}/commodities/{self.customer.commodities.first().pk}/remove/",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.assertEqual(1, self.customer.commodities.count())


class MarketSubscriptionTestCases(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

        for name in COMMODITIES:
            setattr(self, name, Commodity.objects.create(
                name=name,
                short_name=name[:14])
            )

        self.commodity = Commodity.objects.first()
        self.customer = CustomerFactory(
            blank=True,
            is_registered=True,
            name="IsRegistered",
            sex=SEX.FEMALE,
            commodities=[self.commodity]
        )
        self.market_subscription = MarketSubscriptionFactory(
            customer=self.customer,
            commodity=self.commodity
        )

    def test_setup(self):
        self.assertTrue(self.customer.is_registered)
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(1, self.customer.commodities.count())
        self.assertEqual(1, self.customer.market_subscriptions.count())

    def test_logged_in_list_marketsubscriptions_renders(self):
        response = self.client.get(
            reverse("customers:customer_market_subscription_list", args=[self.customer.pk]),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertIn('customers/marketpricesubscription_list.html', response.template_name)

    def test_logged_out_list_marketsubscriptions_redirects(self):
        self.client.logout()
        response = self.client.get(
            reverse("customers:customer_market_subscription_list", args=[self.customer.pk]),
            follow=True
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.pk}/markets/",
            status_code=302,
            target_status_code=200,
        )
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_create_marketsubscriptions_renders(self):
        response = self.client.get(
            reverse('customers:customer_market_subscription_create', args=[self.customer.pk]),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['customers/marketpricesubscription_form.html'], response.template_name)

    def test_logged_out_create_marketsubscriptions_redirects(self):
        self.client.logout()
        response = self.client.get(
            reverse("customers:customer_market_subscription_create", args=[self.customer.pk]),
            follow=True
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.pk}/markets/new/",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_get_marketsubscriptions_delete_rejects(self):
        # Starting in django 4, delete must be as a result of a post, not a get
        response = self.client.get(
            reverse(
                "customers:customer_market_subscription_delete",
                args=[self.customer.pk, self.customer.market_subscriptions.first().pk],
            ),
            follow=True,
        )
        self.assertEqual(405, response.status_code)
        self.assertEqual(1, self.customer.market_subscriptions.count())  # Commodity was not removed

    def test_logged_in_post_marketsubscriptions_delete_succeeds(self):
        response = self.client.post(
            reverse(
                "customers:customer_market_subscription_delete",
                args=[self.customer.pk, self.customer.market_subscriptions.first().pk],
            ),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.is_rendered)
        self.assertIn('customers/marketpricesubscription_list.html', response.template_name)
        # get message from context and check that expected text is there
        message = list(response.context.get('messages'))[0]
        self.assertEqual("success", message.tags)
        self.assertTrue("was deleted" in message.message)
        self.assertEqual(0, self.customer.market_subscriptions.count())  # Object is deleted

    def test_logged_out_marketsubscriptions_delete_redirects(self):
        self.client.logout()
        response = self.client.get(
            reverse(
                "customers:customer_market_subscription_delete",
                args=[self.customer.pk, self.customer.market_subscriptions.first().pk],
            ),
            follow=True,
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.id}/markets/{self.customer.market_subscriptions.first().pk}/delete/",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.assertEqual(1, self.customer.market_subscriptions.count())

    def test_logged_out_post_marketsubscriptions_delete_redirects(self):
        self.client.logout()
        response = self.client.post(
            reverse(
                "customers:customer_market_subscription_delete",
                args=[self.customer.pk, self.customer.market_subscriptions.first().pk],
            ),
            follow=True,
        )
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/customers/customer/{self.customer.id}/markets/{self.customer.market_subscriptions.first().pk}/delete/",
            status_code=302,
            target_status_code=200,
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)
        self.assertEqual(1, self.customer.market_subscriptions.count())
