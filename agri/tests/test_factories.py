from core.test.cases import TestCase

from . import factories
from .. import models


class AgriculturalRegionFactoryTestCase(TestCase):
    def test_can_create_region_from_factory(self):
        factories.AgriculturalRegionFactory()
        self.assertEqual(models.Region.objects.count(), 1)


class CommodityFactoryTestCase(TestCase):
    def test_can_create_commodity_from_factory(self):
        factories.CommodityFactory()
        self.assertEqual(models.Commodity.objects.count(), 1)

    def test_can_create_commodity_with_event_based_livestock_trait(self):
        commodity = factories.CommodityFactory(event_based_livestock=True)
        self.assertEqual(commodity.commodity_type, models.Commodity.LIVESTOCK)
        self.assertTrue(commodity.is_event_based)
        self.assertIsNotNone(commodity.fallback_commodity)

    def test_can_create_commodity_with_seasonal_livestock_trait(self):
        commodity = factories.CommodityFactory(seasonal_livestock=True)
        self.assertEqual(commodity.commodity_type, models.Commodity.LIVESTOCK)
        self.assertFalse(commodity.is_event_based)
        self.assertIsNone(commodity.fallback_commodity)

    def test_can_create_commodity_with_crop_trait(self):
        commodity = factories.CommodityFactory(crop=True)
        self.assertEqual(commodity.commodity_type, models.Commodity.CROP)
        self.assertIsNone(commodity.fallback_commodity)
