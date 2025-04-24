from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from dateutil.relativedelta import relativedelta
from gateways.africastalking.testing import activate_success_response

from django_tenants.test.client import TenantClient as Client
from core.test.cases import TestCase
from core.tests.utils import UploadCSVFileMixin, UserAuthenticationMixin
from customers.tests.factories import CustomerFactory, CustomerCategoryFactory, PremiumCustomerFactory, SubscriptionFactory
from sms.models import OutgoingSMS, SMSRecipient
from world.models import Border

from ..models import _this_month, CountyForecast
from ..tasks import send_forecast_for_county, send_weather_forecasts
from .factories import CountyForecastFactory


@patch("celery.app.task.denied_join_result")
@override_settings(SEND_SMS=True, CELERY_TASK_ALWAYS_EAGER=True)
class CountyForecastSendingTests(TestCase):

    def setUp(self):
        super().setUp()
        # Make 2 subscribed (premium) customers, and 2 unsubscribed (freemium)
        # Add a category to one of each
        self.category = CustomerCategoryFactory()
        # Create customer 1 with a random county
        self.c1 = PremiumCustomerFactory(
            categories=[self.category], border1=Border.kenya_counties.order_by("?").first()
        )
        # Create customer 2 with a different county
        self.c2 = PremiumCustomerFactory(
            border1=Border.kenya_counties.exclude(id=self.c1.border1.id).order_by("?").first()
        )

        # Create 2 customers with the same counties as above, but freemium accounts
        self.c3 = CustomerFactory(
            categories=[self.category], border1=self.c1.border1,
        )
        self.c4 = CustomerFactory(
            border1=self.c2.border1,
        )

        # Create county forecasts for combinations of customers
        # CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=True)   # self.c1 only
        # CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=False)  # self.c1 and self.c3
        # CountyForecastFactory(county=self.c2.border1, premium_only=True)   # self.c2 only
        # CountyForecastFactory(county=self.c2.border1, premium_only=False)  # self.c2 and self.c4

    @activate_success_response
    def test_sending_forecast_for_one_county_premium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, premium_only=True)
        county_id = self.c1.border1_id
        send_forecast_for_county.delay('fast_test', county_id,)
        self.assertEqual(1, OutgoingSMS.objects.count())  # Only 1 premium subscriber in this county
        self.assertEqual(1, SMSRecipient.objects.count())
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(1, smss.count())
        # Ensure the recipients are connected correctly
        self.assertEqual(1, smss.first().recipients.count())

    @activate_success_response
    def test_sending_forecast_for_one_county_freemium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, premium_only=False)
        county_id = self.c1.border1_id
        send_forecast_for_county.delay('fast_test', county_id,)
        self.assertEqual(1, OutgoingSMS.objects.count())  # Two customers in this county
        self.assertEqual(2, SMSRecipient.objects.count())
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(1, smss.count())
        # Ensure the recipients are connected correctly
        self.assertEqual(2, smss.first().recipients.count())

    @activate_success_response
    def test_sending_forecast_for_one_category_premium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=True)
        county1_id = self.c1.border1_id
        send_forecast_for_county.delay('fast_test', county1_id,)
        self.assertEqual(1, OutgoingSMS.objects.count())  # Two customers with this category / county combination
        self.assertEqual(1, SMSRecipient.objects.count())
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(1, smss.count())
        sms1 = smss.first()
        # Ensure the category_name field is set in the OutgoingSMS
        self.assertEqual(self.category.name, sms1.extra['category_name'])
        # Ensure the recipients are connected correctly
        self.assertEqual(1, sms1.recipients.count())
        self.assertEqual(self.c1, sms1.recipients.first().recipient)

        county2_id = self.c2.border1_id
        send_forecast_for_county.delay('fast_test', county2_id,)  # Not in this category
        # No new messages sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())  # 2 customers with this county
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(1, smss.count())

    @activate_success_response
    def test_sending_forecast_for_one_category_freemium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=False)
        county1_id = self.c1.border1_id
        send_forecast_for_county.delay('fast_test', county1_id,)
        self.assertEqual(1, OutgoingSMS.objects.count())  # Two customers with this category / county combination
        self.assertEqual(2, SMSRecipient.objects.count())
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(1, smss.count())
        sms1 = smss.first()
        # Ensure the category_name field is set in the OutgoingSMS
        self.assertEqual(self.category.name, sms1.extra['category_name'])
        # Ensure the recipients are connected correctly
        self.assertEqual(2, sms1.recipients.count())
        self.assertIn(self.c1.id, sms1.recipients.values_list('recipient__id', flat=True))
        self.assertIn(self.c3.id, sms1.recipients.values_list('recipient__id', flat=True))

        county2_id = self.c2.border1_id
        send_forecast_for_county.delay('fast_test', county2_id,)  # Not in this category
        # No new messages sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())  # 2 customers with this county
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(1, smss.count())

    @activate_success_response
    @patch("weather.tasks.client_setting")
    def test_sending_forecasts_for_today(self, mocked_join_result, mocked_client_setting):
        mocked_client_setting.return_value = True # mock enabling weather sending
        # Create county forecasts for combinations of all customers
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=True)   # self.c1 only
        CountyForecastFactory(county=self.c2.border1, premium_only=False)  # self.c2 and self.c4
        send_weather_forecasts.delay()
        self.assertEqual(2, OutgoingSMS.objects.count())   # One from category filter, one not
        self.assertEqual(3, SMSRecipient.objects.count())  # One from category filter, two from premium_only = False
        # Ensure the message_type is set correctly
        smss = OutgoingSMS.objects.filter(message_type='wxke')
        self.assertEqual(2, smss.count())
        # Ensure the recipients are connected correctly
        sms1 = smss.get(extra__county_id=self.c1.border1.id)
        self.assertEqual(1, sms1.recipients.count())
        self.assertIn(self.c1.id, sms1.recipients.values_list('recipient__id', flat=True))
        self.assertNotIn(self.c2.id, sms1.recipients.values_list('recipient__id', flat=True))
        self.assertNotIn(self.c3.id, sms1.recipients.values_list('recipient__id', flat=True))
        self.assertNotIn(self.c4.id, sms1.recipients.values_list('recipient__id', flat=True))
        # Ensure the recipients are connected correctly
        sms2 = smss.get(extra__county_id=self.c2.border1.id)
        self.assertEqual(2, sms2.recipients.count())
        self.assertNotIn(self.c1.id, sms2.recipients.values_list('recipient__id', flat=True))
        self.assertIn(self.c2.id, sms2.recipients.values_list('recipient__id', flat=True))
        self.assertNotIn(self.c3.id, sms2.recipients.values_list('recipient__id', flat=True))
        self.assertIn(self.c4.id, sms2.recipients.values_list('recipient__id', flat=True))

    @activate_success_response
    @patch("weather.tasks.client_setting")
    def test_repeated_calls_no_category_freemium(self, mocked_join_result, mocked_client_setting):
        mocked_client_setting.return_value = True # mock enabling weather sending
        CountyForecastFactory(county=self.c1.border1, premium_only=False)   # self.c1 & self.c3
        send_weather_forecasts.delay()
        self.assertEqual(1, OutgoingSMS.objects.count())   # One from category filter, one not
        self.assertEqual(2, SMSRecipient.objects.count())  # There's something for everyone

        # Call again
        send_weather_forecasts.delay()
        # No duplicates should be sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())

    @activate_success_response
    @patch("weather.tasks.client_setting")
    def test_repeated_calls_category_freemium(self, mocked_join_result, mocked_client_setting):
        mocked_client_setting.return_value = True # mock enabling weather sending
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=False)   # self.c1 & self.c3
        send_weather_forecasts.delay()
        self.assertEqual(1, OutgoingSMS.objects.count())   # One from category filter, one not
        self.assertEqual(2, SMSRecipient.objects.count())  # There's something for everyone

        # Call again
        send_weather_forecasts.delay()
        # No duplicates should be sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(2, SMSRecipient.objects.count())

    @activate_success_response
    @patch("weather.tasks.client_setting")
    def test_repeated_calls_category_premium(self, mocked_join_result, mocked_client_setting):
        mocked_client_setting.return_value = True # mock enabling weather sending
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=True)   # self.c1 only
        send_weather_forecasts.delay()
        self.assertEqual(1, OutgoingSMS.objects.count())   # One from category filter, one not
        self.assertEqual(1, SMSRecipient.objects.count())  # There's something for everyone

        # Call again
        send_weather_forecasts.delay()
        # No duplicates should be sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())

    @activate_success_response
    def test_date_in_future_no_category_freemium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, premium_only=False)  # self.c1 & self.c3
        future_date = timezone.now().date() + relativedelta(months=2)
        send_weather_forecasts.delay(date=future_date)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_date_in_future_category_freemium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=False)  # self.c1 & self.c3
        future_date = timezone.now().date() + relativedelta(months=2)
        send_weather_forecasts.delay(date=future_date)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_date_in_future_category_premium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=True)  # self.c1 only
        future_date = timezone.now().date() + relativedelta(months=2)
        send_weather_forecasts.delay(date=future_date)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_date_in_past_no_category_freemium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, premium_only=False)  # self.c1 & self.c3
        past_date = timezone.now().date() + relativedelta(months=-2)
        send_weather_forecasts.delay(date=past_date)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_date_in_past_category_freemium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=False)  # self.c1 & self.c3
        past_date = timezone.now().date() + relativedelta(months=-2)
        send_weather_forecasts.delay(date=past_date)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_date_in_past_category_premium(self, mocked_join_result):
        CountyForecastFactory(county=self.c1.border1, add_category=self.category, premium_only=True)  # self.c1 only
        past_date = timezone.now().date() + relativedelta(months=-2)
        send_weather_forecasts.delay(date=past_date)
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @activate_success_response
    def test_do_not_send_future_forecasts(self, mocked_join_result):
        future_date = timezone.now().date() + relativedelta(months=2)
        # Make forecasts for each county
        # TODO: i18n
        for county in Border.kenya_counties:
            CountyForecastFactory(county=county, dates=_this_month(future_date))

        send_weather_forecasts.delay()

        # No forecasts should have been sent
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())


class CountyForecastImportingTests(UploadCSVFileMixin, UserAuthenticationMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)
        self.create_superuser()

    def test_valid_import_county_name_no_category(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo', 'There will be weather', '2023-02-06', '2023-02-13')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(len(file_rows)-1, CountyForecast.objects.count())
        cf = CountyForecast.objects.first()
        self.assertEqual(file_rows[1][0], cf.county.name)
        self.assertEqual(file_rows[1][1], cf.text)
        self.assertEqual(file_rows[1][2], cf.dates.lower.isoformat())
        self.assertEqual(file_rows[1][3], cf.dates.upper.isoformat())

    def test_valid_import_county_number_no_category(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            (2, 'There will be weather', '2023-02-06', '2023-02-13')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(len(file_rows)-1, CountyForecast.objects.count())
        cf = CountyForecast.objects.first()
        self.assertEqual(file_rows[1][0], cf.county.id)
        self.assertEqual(file_rows[1][1], cf.text)
        self.assertEqual(file_rows[1][2], cf.dates.lower.isoformat())
        self.assertEqual(file_rows[1][3], cf.dates.upper.isoformat())

    def test_valid_import_one_category_by_name(self):
        category = CustomerCategoryFactory()
        file_rows = [
            ('county', 'text', 'start', 'end', 'category'),
            ('Baringo', 'There will be weather', '2023-02-06', '2023-02-13', category.name)
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(len(file_rows)-1, CountyForecast.objects.count())
        cf = CountyForecast.objects.first()
        self.assertEqual(file_rows[1][0], cf.county.name)
        self.assertEqual(file_rows[1][1], cf.text)
        self.assertEqual(file_rows[1][2], cf.dates.lower.isoformat())
        self.assertEqual(file_rows[1][3], cf.dates.upper.isoformat())
        self.assertEqual(category.name, cf.category.name)
        self.assertEqual(category.id, cf.category.id)

    def test_valid_import_one_category_by_number(self):
        category = CustomerCategoryFactory()
        file_rows = [
            ('county', 'text', 'start', 'end', 'category'),
            ('Baringo', 'There will be weather', '2023-02-06', '2023-02-13', category.id)
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(len(file_rows)-1, CountyForecast.objects.count())
        cf = CountyForecast.objects.first()
        self.assertEqual(file_rows[1][0], cf.county.name)
        self.assertEqual(file_rows[1][1], cf.text)
        self.assertEqual(file_rows[1][2], cf.dates.lower.isoformat())
        self.assertEqual(file_rows[1][3], cf.dates.upper.isoformat())
        self.assertEqual(category.name, cf.category.name)
        self.assertEqual(category.id, cf.category.id)

    def test_import_two_categories_as_one_fails(self):
        category1 = CustomerCategoryFactory()
        category2 = CustomerCategoryFactory()
        file_rows = [
            ('county', 'text', 'start', 'end', 'category'),
            ('Baringo', 'There will be weather', '2023-02-06', '2023-02-13', f'{category1.name},{category2.name}')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'<ul class="errorlist"><li>The category {category1.name},{category2.name} does not exist.</li></ul>'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_two_categories_as_two_fails(self):
        category1 = CustomerCategoryFactory()
        category2 = CustomerCategoryFactory()
        file_rows = [
            ('county', 'text', 'start', 'end', 'category', 'premium_only'),
            ('Baringo','There will be weather', '2023-02-06', '2023-02-13', category1.name, category2.name, 'true')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'Invalid row: Number of columns ({len(file_rows[1])}) does not match number of headers ({len(file_rows[0])}).'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_empty_text_fails(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo','', '2023-02-06', '2023-02-13')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'The text field cannot be empty on row 2 of imported spreadsheet'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_no_text_fails(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo', None, '2023-02-06', '2023-02-13')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'The text field cannot be empty on row 2 of imported spreadsheet'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_empty_start_fails(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo', 'There will be weather', '', '2023-02-13')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'The start field cannot be empty on row 2 of imported spreadsheet'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_no_start_fails(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo', 'There will be weather', None, '2023-02-13')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'The start field cannot be empty on row 2 of imported spreadsheet'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_empty_end_fails(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo', 'There will be weather', '2023-02-06', '')
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'The end field cannot be empty on row 2 of imported spreadsheet'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_import_no_end_fails(self):
        file_rows = [
            ('county', 'text', 'start', 'end'),
            ('Baringo', 'There will be weather', '2023-02-06', None)
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            f'The end field cannot be empty on row 2 of imported spreadsheet'
        )
        self.assertEqual(0, CountyForecast.objects.count())

    def test_valid_import_reordered_columns(self):
        category = CustomerCategoryFactory()
        file_rows = [
            ('premium_only', 'text', 'end', 'county', 'start', 'category'),
            ('True', 'There will be weather', '2023-02-13', 'Baringo', '2023-02-06', category.name)
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(len(file_rows)-1, CountyForecast.objects.count())
        cf = CountyForecast.objects.first()
        self.assertEqual(file_rows[1][3], cf.county.name)
        self.assertEqual(file_rows[1][1], cf.text)
        self.assertEqual(file_rows[1][4], cf.dates.lower.isoformat())
        self.assertEqual(file_rows[1][2], cf.dates.upper.isoformat())
        self.assertEqual(file_rows[1][5], category.name)
        self.assertTrue(cf.premium_only)

    def test_valid_import_unknown_columns(self):
        category = CustomerCategoryFactory()
        file_rows = [
            ('foo', 'bar', 'baz', 'goober'),
            ('True', 'There will be weather', '2023-02-13', 'Baringo', '2023-02-06', category.name)
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, CountyForecast.objects.count())
        self.assertContains(response, 'The first row of the input file must contain the column headers')

    def test_valid_import_mismatched_columns_and_data(self):
        category = CustomerCategoryFactory()
        file_rows = [
            ('premium_only', 'text', 'end', 'county', 'start'),
            ('True', 'There will be weather', '2023-02-13', 'Baringo', '2023-02-06', category.name)
        ]
        test_file = self.generate_csv_file(*file_rows)
        post_data = {
            'file': test_file,
            'input_format': 0  # CSV
        }
        url = reverse('weather:county_forecast_upload')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, CountyForecast.objects.count())
        self.assertContains(response, f'Invalid row: Number of columns ({len(file_rows[1])}) does not match number of headers ({len(file_rows[0])}).')
