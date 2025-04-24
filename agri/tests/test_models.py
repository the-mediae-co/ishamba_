from django.core.exceptions import ValidationError
from unittest import skip

from core.test.cases import TestCase

from agri import constants
from agri.models.base import Commodity

from ..models import AgriTipSMS
from .factories import AgriTipSMSFactory
from .utils import CommodityTestCaseMixin


class CommodityModelTestCase(TestCase, CommodityTestCaseMixin):
    """ Tests that commodities behave correctly according to their commodity
    types.
    """
    def setUp(self):
        super().setUp()
        self.create_commodities()

    def test_is_event_based_flag(self):
        vals = (('maize', False), ('cow', False), ('calf', True))

        for name, expectation in vals:
            commodity = Commodity.objects.get(name=name)
            self.assertEqual(commodity.is_event_based, expectation)

    def test_fallback_commodity_foreign_key(self):
        vals = (('maize', None), ('carrots', None), ('calf', self.cow), ('lamb', self.sheep))

        for name, expectation in vals:
            commodity = Commodity.objects.get(name=name)
            self.assertEqual(expectation, commodity.fallback_commodity)

    def test_variant_of_foreign_key(self):
        vals = (('maize', None), ('carrots', None), ('calf', self.cow), ('lamb', self.sheep))

        for name, expectation in vals:
            commodity = Commodity.objects.get(name=name)
            self.assertEqual(expectation, commodity.variant_of)

    def test_calendar_type_property(self):
        vals = (('maize', constants.CALENDAR_TYPE_SEASONAL),
                ('cow', constants.CALENDAR_TYPE_SEASONAL),
                ('calf', constants.CALENDAR_TYPE_EVENT_BASED))

        for name, expectation in vals:
            commodity = Commodity.objects.get(name=name)
            self.assertEqual(commodity.calendar_type, expectation)

    def test_event_based_must_have_fallback(self):
        with self.assertRaises(ValidationError):
            commodity = Commodity.objects.create(name='new', short_name='new',
                                                 epoch_description='an event')
            commodity.clean()

    def test_fallback_may_not_be_event_based(self):
        fallback = Commodity.objects.get(name='calf')

        with self.assertRaises(ValidationError):
            commodity = Commodity.objects.create(name='new', short_name='new',
                                                 epoch_description='an event',
                                                 fallback_commodity=fallback)
            commodity.clean()

    def test_seasonal_may_not_have_fallback(self):
        fallback = Commodity.objects.get(name='calf')

        with self.assertRaises(ValidationError):
            commodity = Commodity.objects.create(name='new', short_name='new',
                                                 fallback_commodity=fallback)
            commodity.clean()


class AgriTipSMSTestCase(TestCase):

    @skip("AgriTipSMS is Deprecated")
    def test_cant_create_regionless_agritip_with_same_commodity_and_tip_number(self):
        tip = AgriTipSMSFactory(region=None,
                                commodity__commodity_type=Commodity.LIVESTOCK)
        with self.assertRaises(ValidationError):
            duplicate = AgriTipSMS.objects.create(region=None,
                                                  commodity=tip.commodity,
                                                  number=tip.number,
                                                  text='foo')
            duplicate.clean_fields()

    @skip("AgriTipSMS is Deprecated")
    def test_cant_create_agritip_with_non_gsm_chars(self):
        with self.assertRaises(ValidationError):
            ats = AgriTipSMSFactory(text='`')
            ats.clean_fields()
