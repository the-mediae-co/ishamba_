from django.urls import reverse
from django_tenants.test.client import TenantClient as Client

from core.test.cases import TestCase

from agri.tests.factories import CommodityFactory
from customers.tests.factories import (CustomerFactory, CustomerPhoneFactory, SubscriptionFactory,
                                       SubscriptionAllowanceFactory, SubscriptionTypeFactory)
from markets.tests.factories import MarketFactory

from .utils import UploadCSVFileMixin, UserAuthenticationMixin


class MarketPriceImportTestCase(UploadCSVFileMixin, UserAuthenticationMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)
        self.create_user()

        self.commodity = CommodityFactory(crop=True)
        self.market = MarketFactory()

        self.import_url = reverse('admin:markets_marketprice_import')

    def test_valid_upload(self):
        test_file = self.generate_csv_file(
            ('Date', 'Category', 'Commodity', '', 'Capacity', 'Unit', 'Price', 'Market'),
            ('05.07.2016', 'CEREALS', self.commodity.name, 'Bag', '90', 'Kgs', '2700', self.market.name)
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertFalse(response.context['result'].has_errors())


class MarketSubscriptionImportTestCase(UploadCSVFileMixin, UserAuthenticationMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)
        self.create_user()

        self.commodity = CommodityFactory(crop=True)
        self.market = MarketFactory()
        self.backup = MarketFactory(is_main_market=True)
        self.customer = CustomerFactory(
            blank=True, has_no_phones=True, has_no_subscriptions=True, has_no_markets=True, commodities=[self.commodity]
        )
        self.phones = CustomerPhoneFactory(customer=self.customer, is_main=True)

        self.sub_type = SubscriptionTypeFactory()
        SubscriptionAllowanceFactory(code='prices', type=self.sub_type)
        SubscriptionAllowanceFactory(code='markets', type=self.sub_type)
        SubscriptionAllowanceFactory(code='tips', type=self.sub_type)
        SubscriptionFactory(customer=self.customer, type=self.sub_type)

        self.import_url = reverse('admin:markets_marketsubscription_import')

    def test_valid_upload(self):
        test_file = self.generate_csv_file(
            ('customer', 'market', 'backup', 'commodity'),
            (self.customer.id, self.market.name, self.backup.name, self.commodity.name)
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        print(response.rendered_content)
        self.assertFalse(response.context['result'].has_errors())
