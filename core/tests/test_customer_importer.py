import logging
from tablib import Dataset

from django.urls import reverse
from core.importer.resources import CustomerImportResource
from core.constants import SEX

from django_tenants.test.client import TenantClient as Client

from core.test.cases import TestCase

from agri.tests.factories import CommodityFactory, AgriculturalRegionFactory
from customers.constants import JOIN_METHODS
from customers.models import Customer, CustomerPhone
from world.models import Border

from .utils import UploadCSVFileMixin, UserAuthenticationMixin

logger = logging.getLogger(__name__)

CUSTOMER_CSV_HEADER = (
    'name', 'sex', 'phones', 'village', 'ward',
    'subcounty', 'county', 'country', 'agricultural_region',
    'preferred_language', 'farm_size', 'notes',
    'commodities', 'categories', 'location')


class CustomerImportTestCase(UploadCSVFileMixin, UserAuthenticationMixin,
                             TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)

        self.create_user()

        self.agricultural_region = AgriculturalRegionFactory(name='Central Region')

        self.kenya_border3 = Border.objects.filter(country='Kenya', level=3).order_by('?').first()
        self.kenya_border2 = self.kenya_border3.parent
        self.kenya_border1 = self.kenya_border2.parent
        self.kenya_border0 = self.kenya_border1.parent

        # self.uganda_border3 = Border.objects.filter(country='Uganda', level=3).order_by('?').first()
        self.uganda_border3 = Border.objects.filter(country='Uganda', level=3, name='Sheema').first()
        self.uganda_border2 = self.uganda_border3.parent
        self.uganda_border1 = self.uganda_border2.parent
        self.uganda_border0 = self.uganda_border1.parent

        self.tomatoes = CommodityFactory(name='Tomatoes', crop=True)
        self.potatoes = CommodityFactory(name='Potatoes', crop=True)

        self.import_url = reverse('admin:customers_customer_import')
        self.process_import_url = reverse('admin:customers_customer_process_import')

    def test_valid_import(self):
        # self.client.login(username=self.user.username, password=self.password)
        phones = '+254700000000'
        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, phones, '', '', '', '', '',
             str(self.agricultural_region.pk), 'swa', '', '', str(self.tomatoes.pk),
             '', "36.863250732421875, -1.2729360401038594")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_import: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_valid_import_multiple_numbers(self):
        # self.client.login(username=self.user.username, password=self.password)
        phones = '+254700000000,+254700000001,+254700000002, +254700000003'
        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, phones, '', '', '', '', '',
             str(self.agricultural_region.pk), 'swa', '', '', str(self.tomatoes.pk),
             '', "36.863250732421875, -1.2729360401038594")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_import_multiple_numbers: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_valid_kenya_import_using_uganda_border_headers(self):
        phones = '+254700000000'
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'county',
            'district', 'region', 'country', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Jane Doe', SEX.MALE, phones, '', '', '', '', '',
             str(self.agricultural_region.pk), 'eng', '', '', str(self.tomatoes.pk),
             '', "32.023247, 0.375680")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_kenya_import_using_uganda_border_headers: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_valid_import_using_generic_border_headers(self):
        phones = '+254700000000'
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'border0',
            'border1', 'border2', 'border3', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Jane Doe', SEX.FEMALE, phones, 'village', 'kenya', '', '', '',
             str(self.agricultural_region.pk), 'eng', '', '', str(self.tomatoes.pk),
             '', "36.863250732421875, -1.2729360401038594")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_import_using_generic_border_headers: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_valid_import_uganda_using_generic_border_headers_wrong_order(self):
        phones = '+256700000000'
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'border3',
            'border2', 'border1', 'border0', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Jane Doe', SEX.FEMALE, phones, 'ugandavillage',
             str(self.uganda_border3.name), str(self.uganda_border2.name), str(self.uganda_border1.name), str(self.uganda_border0.name),
             str(self.agricultural_region.pk), 'eng', '', '', str(self.tomatoes.pk),
             '', "36.863250732421875, -1.2729360401038594")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_import_uganda_using_generic_border_headers_wrong_order: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())
        self.assertEqual(0, len(response.context['result'].invalid_rows))
        # match = [i for i in response.context['result'].invalid_rows[0].error.messages if 'Unknown country for administrative unit' in i]
        # self.assertTrue(match)

    def test_valid_import_uganda_using_generic_border_headers_right_order(self):
        phones = '+256700000000'
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'border0',
            'border1', 'border2', 'border3', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Jane Doe', SEX.FEMALE, phones, 'ugandavillage',
             str(self.uganda_border0.name), str(self.uganda_border1.name), str(self.uganda_border2.name), str(self.uganda_border3.name),
             str(self.agricultural_region.pk), 'eng', '', '', str(self.tomatoes.pk),
             '', "36.863250732421875, -1.2729360401038594")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_import_uganda_using_generic_border_headers_right_order: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_valid_customer_join_method(self):
        phones = '+254720123456,+254720123457'
        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.MALE, phones, '', '', '', '', '',
             str(self.agricultural_region.pk), 'swa', '', '', str(self.tomatoes.pk),
             '', "36.863250732421875, -1.2729360401038594")
        )
        customer_import_resource = CustomerImportResource()
        dataset = Dataset().load(test_file.read().decode(), format='csv')
        customer_import_resource.import_data(dataset=dataset, dry_run=False)
        main_phone = phones.split(',')[0].strip()
        c = Customer.objects.get(phones__number=main_phone)
        self.assertEqual(JOIN_METHODS.IMPORT, c.join_method)
        self.assertEqual(1, Customer.objects.count())
        self.assertEqual(2, CustomerPhone.objects.count())
        self.assertTrue(Customer.objects.filter(name='Jane Doe').exists())

    def test_invalid_language_choice(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county, country
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somewhere', str(self.kenya_border3.pk), str(self.kenya_border2.pk), str(self.kenya_border1.pk), str(self.kenya_border0.pk),
             str(self.agricultural_region.pk), 'Q', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_invalid_language_choice: {row.error.messages}")
        self.assertTrue(response.context['result'].has_validation_errors())
        self.assertIn(
            'is not a valid choice',
            response.context['result'].invalid_rows[0].error.messages[0])

    def test_valid_language_name(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county, country
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location
        CUSTOMER_CSV_HEADER = (
            'name', 'sex', 'phones', 'village', 'ward',
            'subcounty', 'county', 'country', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somewhere', str(self.kenya_border3.pk), str(self.kenya_border2.pk), str(self.kenya_border1.pk), str(self.kenya_border0.pk),
             str(self.agricultural_region.pk), 'English', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_valid_language_name: {row.error.messages}")
        # if response.context['result'].has_errors():
        #     print(f"test_valid_language_name: {response.rendered_content}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_geography_import_by_pk(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.MALE, '+254700000000',
             'somevillage', self.kenya_border3.pk, self.kenya_border2.pk, self.kenya_border1.pk, self.kenya_border0.pk,
             self.agricultural_region.pk, 'eng', '', '', self.tomatoes.pk,
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_geography_import_by_pk: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_geography_import_by_kenya_names(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county, country,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somevillage', self.kenya_border3.name, self.kenya_border2.name, self.kenya_border1.name, self.kenya_border0.name,
             self.agricultural_region.name, 'swa', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        #First, the dry_run
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_geography_import_by_kenya_names: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_geography_import_by_uganda_names(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county, country,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'county',
            'district', 'region', 'country', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Jane Doe', SEX.FEMALE, '+256700000000,+256700000001', 'somevillage',
             self.uganda_border3.name, self.uganda_border2.name, self.uganda_border1.name, self.uganda_border0.name,
             self.agricultural_region.name, 'eng', '', '', str(self.tomatoes.pk),
             '', '32.023247, 0.375680')
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        #First, the dry_run
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_geography_import_by_uganda_names: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_geography_import_by_mixedcase_names(self):
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'COUNTRY', 'cOUNTY', 'sUbCoUnTy', 'Ward',
            'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somevillage', self.kenya_border0.name, self.kenya_border1.name, self.kenya_border2.name, self.kenya_border3.name,
             self.agricultural_region.name, 'swa', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        #First, the dry_run
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_geography_import_by_mixedcase_names: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_geography_import_by_pk_str(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somevillage', str(self.kenya_border3.pk), str(self.kenya_border2.pk), str(self.kenya_border1.pk), str(self.kenya_border0.pk),
             str(self.agricultural_region.pk), 'eng', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_geography_import_by_pk_str: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_geography_import_with_empty_fields(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location,

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somevillage', '', '', '', '',
             '', 'swa', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_geography_import_with_empty_fields: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_commodity_import_by_name(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somevillage', self.kenya_border3.name, self.kenya_border2.name, self.kenya_border1.name, self.kenya_border0.name,
             self.agricultural_region.name, 'eng', '', '', str(self.tomatoes.name),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_commodity_import_by_name: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_multiple_commodity_import_by_name(self):
        # Input format:
        # name, sex, phones, village, ward, subcounty, county,
        # agricultural_region, preferred_language, farm_size, notes, commodities,
        # categories, location

        test_file = self.generate_csv_file(
            CUSTOMER_CSV_HEADER,
            ('Jane Doe', SEX.FEMALE, '+254700000000',
             'somevillage', self.kenya_border3.name, self.kenya_border2.name, self.kenya_border1.name, self.kenya_border0.name,
             self.agricultural_region.name, 'swa', '', '', f"{self.tomatoes.name},{self.potatoes.name}",
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_multiple_commodity_import_by_name: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())

    def test_invalid_import_multiple_countries(self):
        # Uganda headers
        customer_csv_header = (
            'name', 'sex', 'phones', 'village', 'county',
            'district', 'region', 'country', 'agricultural_region',
            'preferred_language', 'farm_size', 'notes',
            'commodities', 'categories', 'location')
        test_file = self.generate_csv_file(
            customer_csv_header,
            ('Uganda farmer', SEX.MALE, '+256700000000', 'somevillage',
             self.uganda_border3.name, self.uganda_border2.name, self.uganda_border1.name, self.uganda_border0.name,
             '', 'eng', '', '', str(self.tomatoes.pk),
             '', "32.023247, 0.375680"),
            ('Kenya farmer', SEX.FEMALE, '+254700000000', 'somevillage',
             self.kenya_border3.name, self.kenya_border2.name, self.kenya_border1.name, self.kenya_border0.name,
             str(self.agricultural_region.pk), 'swa', '', '', str(self.tomatoes.pk),
             '', "37.129288, -0.471286")
        )

        post_data = {
            'import_file': test_file,
            'input_format': 0  # CSV
        }
        response = self.client.post(self.import_url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        # for row in response.context['result'].invalid_rows:
        #     print(f"test_invalid_import_multiple_countries: {row.error.messages}")
        self.assertFalse(response.context['result'].has_errors())
        self.assertTrue(response.context['result'].has_validation_errors())
        self.assertEqual(1, len(response.context['result'].invalid_rows))
        match = [i for i in response.context['result'].invalid_rows[0].error.messages if 'is not a valid Country (level 0) in Uganda' in i]
        self.assertTrue(match)
        match = [i for i in response.context['result'].invalid_rows[0].error.messages if 'is not a valid Region (level 1) in Uganda' in i]
        self.assertTrue(match)
        match = [i for i in response.context['result'].invalid_rows[0].error.messages if 'is not a valid District (level 2) in Uganda' in i]
        self.assertTrue(match)
        match = [i for i in response.context['result'].invalid_rows[0].error.messages if 'is not a valid County (level 3) in Uganda' in i]
        self.assertTrue(match)
