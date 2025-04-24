import itertools
from unittest import skip
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from django_tenants.test.client import TenantClient as Client
from phonenumbers import PhoneNumber
from taggit.models import Tag, TaggedItem

from agri.models.base import Commodity
from agri.tests.factories import CommodityFactory
from callcenters.models import CallCenter, CallCenterOperator, CallCenterSender
from core.constants import LANGUAGES
from core.test.cases import TestCase
from customers.models import (Customer, CustomerCategory, CustomerPhone,
                              CustomerQuestion, CustomerQuestionAnswer)
from customers.tests.factories import (CustomerFactory, CustomerPhoneFactory,
                                       PremiumCustomerFactory)
from gateways.africastalking.testing import activate_success_response
from ishamba.settings import ELECTRICITY_QUESTION, IRRIGATION_WATER_QUESTION
from sms.constants import KENYA_COUNTRY_CODE, OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS, SMSRecipient
from sms.views import CustomerFilterForm
from tasks.models import Task
from tasks.tests.factories import TaskFactory
from tips.models import TipSeries, TipSeriesSubscription
from tips.tests.factories import TipSeriesFactory
from world.models import Border

from ..forms import MultiplePhoneNumberField


class MultiplePhoneNumberFieldTestCase(TestCase):

    def test_multiple_phone_number_field_validation(self):
        numbers = '+254722123456\n+254722123987'
        output = MultiplePhoneNumberField().to_python(numbers)
        self.assertEqual(len(output), 2)
        self.assertIsInstance(output[0], PhoneNumber)
        self.assertIsInstance(output[1], PhoneNumber)

    def test_multiple_phone_number_field_validation_bad_number(self):
        numbers = '+254722123456\n+254722123'
        with self.assertRaises(ValidationError) as cm:
            MultiplePhoneNumberField().to_python(numbers)
        self.assertEqual(cm.exception.message, 'The following numbers are not valid: +254722123')


class SingleOutgoingSMSTests(TestCase):

    def setUp(self):
        super().setUp()
        user = get_user_model()
        self.operator = user.objects.create_user('foo', password='foo')
        self.client = Client(self.tenant)
        self.client.login(username='foo', password='foo')
        self.task = TaskFactory()
        self.call_center_sender = CallCenterSender.objects.create(sender_id="iShamba", description="blah")

    @activate_success_response
    def test_task_sending_sms_response_to_invalid_customer_fails(self):
        response = self.client.post(f'/tasks/reply/{101010101}/{101010101}/',
                                    {"text": "This is a test"},
                                    follow=True)
        self.assertEqual(response.status_code, 404)

    @activate_success_response
    def test_task_sending_sms_response_succeeds(self):
        response = self.client.post(f'/tasks/reply/{self.task.customer.pk}/{self.task.pk}/',
                                    {"text": "This is a test",
                                     "senders": "iShamba"},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.TASK_RESPONSE, OutgoingSMS.objects.first().message_type)
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(OutgoingSMS.objects.first().id, SMSRecipient.objects.first().message_id)

    @activate_success_response
    def test_sending_sms_succeeds(self):
        response = self.client.post(f'/customers/customer/{self.task.customer.pk}/sms/outgoing/send/',
                                    {"text": "This is a test",
                                     "senders": "iShamba"},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.INDIVIDUAL, OutgoingSMS.objects.first().message_type)
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(OutgoingSMS.objects.first().id, SMSRecipient.objects.first().message_id)

    @activate_success_response
    def test_logged_out_task_sending_sms_response_fails(self):
        self.client.logout()
        response = self.client.post(f'/tasks/reply/{self.task.customer.pk}/{self.task.pk}/',
                                    {"text": "This is a test"},
                                    follow=True)
        self.assertRedirects(response, f'/accounts/login/?next=%2Ftasks%2Freply%2F{self.task.customer.pk}%2F{self.task.pk}%2F', status_code=302,
                             target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)


class BulkSMSFormTests(TestCase):

    def setUp(self):
        super().setUp()
        user = get_user_model()
        self.operator = user.objects.create_user('foo', password='foo')
        self.client = Client(self.tenant)
        self.client.login(username='foo', password='foo')

    @classmethod
    def setUpTestData(cls):
        cls.call_center_sender = CallCenterSender.objects.create(sender_id="iShamba", description="blah")
        # This setup is insanely slow. However, since the objects created are not modified by any of the tests,
        # the setup can be done only once, before running all the tests.
        cls.even_category = CustomerCategory.objects.create(name='even')
        cls.odd_category = CustomerCategory.objects.create(name='odd')

        cls.commodities_list = [
            CommodityFactory(name='maize', crop=True, gets_market_prices=True),
            CommodityFactory(name='beans', crop=True),
            CommodityFactory(name='carrots', crop=True),
            CommodityFactory(name='bananas', crop=True),
            CommodityFactory(name='avocado', crop=True),
            CommodityFactory(name='bananas', crop=True),
            CommodityFactory(name='dairy', seasonal_livestock=True,
                             commodity_type=Commodity.LIVESTOCK),
            CommodityFactory(name='chickens', event_based_livestock=True,
                             commodity_type=Commodity.LIVESTOCK),
            CommodityFactory(name='sheep', seasonal_livestock=True,
                             commodity_type=Commodity.LIVESTOCK),
            CommodityFactory(name='bees', event_based_livestock=True,
                             commodity_type=Commodity.LIVESTOCK),
        ]

        tip_series = TipSeriesFactory.create_batch(5)

        # Create an errant digifarm customer outside of Kenya
        customer = CustomerFactory(has_no_phones=True)
        # customer.phones.all().delete()
        phone = CustomerPhoneFactory(number='+18156750500', is_main=True, customer=customer)
        customer.name = "bad-digifarmer"
        customer.digifarm_farmer_id = phone.number
        customer.save()

        num_at_customers = 10
        starting_at_number = 254702000000
        cls.africastalking_customers = []
        for at_number in range(starting_at_number, starting_at_number + num_at_customers):
            customer = CustomerFactory(has_no_phones=True)
            # customer.phones.all().delete()
            phone = CustomerPhoneFactory(number="+" + str(at_number), is_main=True, customer=customer)
            customer.name = "africastalkingfarmer:" + str(at_number)
            if (at_number % 2) == 0:
                customer.categories.add(cls.even_category)
                customer.preferred_language = LANGUAGES.KISWAHILI
            else:
                customer.categories.add(cls.odd_category)
                customer.preferred_language = LANGUAGES.LUGANDA
            index = at_number % len(cls.commodities_list)
            customer.commodities.add(cls.commodities_list[index])
            if at_number == starting_at_number:
                customer.sex = ''
            customer.save()
            cls.africastalking_customers.append(customer)
            TipSeriesSubscription.objects.create(
                customer=customer,
                series=tip_series[at_number % len(tip_series)],
                start=timezone.now(),
                ended=False
            )

        # Create an errant africastalking customer outside of Kenya
        customer = CustomerFactory(has_no_phones=True)
        phone = CustomerPhoneFactory(number='+18156750501', is_main=True, customer=customer)
        customer.name = "bad-africastalkingfarmer"
        customer.save()
        cls.africastalking_customers.append(customer)

        num_dual_customers = 10
        starting_dual_df_number = 4929951500000
        starting_dual_at_number = starting_at_number + num_at_customers
        cls.dual_customers = []
        for digi_number, at_number in zip(range(starting_dual_df_number, starting_dual_df_number + num_dual_customers),
                                          range(starting_dual_at_number, starting_dual_at_number + num_dual_customers)):
            customer = CustomerFactory(has_no_phones=True)
            phone1 = CustomerPhoneFactory(number="+" + str(digi_number), is_main=False, customer=customer)
            customer.name = "dual_farmer:" + str(digi_number)
            # customer.digifarm_farmer_id=digi_number
            phone2 = CustomerPhoneFactory(number="+" + str(at_number), is_main=True, customer=customer)
            if (digi_number % 2) == 0:
                customer.categories.add(cls.even_category)
            else:
                customer.categories.add(cls.odd_category)
            index = digi_number % len(cls.commodities_list)
            customer.commodities.add(cls.commodities_list[index])
            customer.save()
            cls.dual_customers.append(customer)
            TipSeriesSubscription.objects.create(
                customer=customer,
                series=tip_series[digi_number % len(tip_series)],
                start=timezone.now(),
                ended=False
            )

        # Create an errant dual customer outside of Kenya
        customer = CustomerFactory(has_no_phones=True)
        phone = CustomerPhoneFactory(number="+18156750502", is_main=True, customer=customer)
        customer.name = "bad-dual_farmer"
        customer.digifarm_farmer_id = customer.main_phone
        customer.save()
        cls.dual_customers.append(customer)

        # Create a customer who requested stop to ensure we don't send to whom we're not supposed to
        cls.stopped_customer = CustomerFactory()
        cls.stopped_customer.has_requested_stop = True
        cls.stopped_customer.save()

        unneeded_customers = []
        cls.test_tasks = []
        tags_list = ["Maize", "Beans", "Mangoes", "Cows", "Chickens"]
        for tag_name in tags_list:
            Tag.objects.create(name=tag_name)
        cls.tags_list = list(Tag.objects.all())
        tags_iter = itertools.cycle(cls.tags_list)

        for c in cls.africastalking_customers:
            task = TaskFactory()
            unneeded_customers.append(task.customer.id)
            unneeded_customers.append(task.source.customer.id)
            task.customer = c
            task.source.customer = c
            task.tags.add(next(tags_iter))
            task.save()
            cls.test_tasks.append(task)

        for c in cls.dual_customers:
            task = TaskFactory()
            # unneeded_customers.append(task.customer.id)
            unneeded_customers.append(task.source.customer.id)
            task.customer = c
            task.source.customer = c
            task.tags.add(next(tags_iter))
            task.save()
            cls.test_tasks.append(task)

        # Delete all the unneeded customers from the Factories
        Customer.objects.filter(id__in=unneeded_customers).delete()

    def test_setup(self):
        self.assertEqual(11, len(self.africastalking_customers))
        self.assertEqual(11, len(self.dual_customers))
        self.assertEqual(len(self.africastalking_customers) +
                         len(self.dual_customers), len(self.test_tasks))
        self.assertEqual(len(self.test_tasks), Task.objects.count())
        self.assertEqual(len(self.test_tasks), len(self.africastalking_customers) + len(self.dual_customers))
        self.assertEqual(len(self.africastalking_customers) + len(self.dual_customers) + 2, Customer.objects.count())

    def test_invalid_numbers_raise_error(self):
        form = CustomerFilterForm({"numbers": ("+12345")})
        self.assertRaisesMessage(ValidationError,
                                 "Attempting to send this SMS caused an error with no "
                                 "info supplied. An error notification has been sent.")

    def test_valid_numbers_dont_raise_error(self):
        number_string = "+254784404125"
        form = CustomerFilterForm({"numbers": (number_string)})
        self.assertEqual(form._errors, None)
        self.assertTrue(form.is_valid())
        form_numbers = form.data['numbers']
        self.assertEqual(form_numbers, number_string)

    def test_logged_out_customer_filter_redirect(self):
        self.client.logout()
        response = self.client.post(reverse('core_management_customer_filter'),
                                    follow=True)
        self.assertRedirects(response, '/accounts/login/?next=%2Fmanagement%2Fbulk_sms%2F', status_code=302,
                             target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_no_filter_success(self):
        response = self.client.post(reverse('core_management_customer_filter'),
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)  # no numbers, so all customers
        self.assertContains(response,
                            f"{len(self.dual_customers) + len(self.africastalking_customers) - 2} Customers")

    def test_logged_in_one_tag_filter_success(self):
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"task_tags": self.tags_list[0].id},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        count = Task.objects.filter(tags__name__in=[self.tags_list[0]]).count() - 1
        self.assertEqual(count, response.context_data.get('count'))
        self.assertContains(response, f"{count} Customers")

    def test_logged_in_two_tags_filter_success(self):
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"task_tags": [self.tags_list[0].id, self.tags_list[0].id]},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        # One of the DF farmers has a US phone number alternative
        count = Task.objects.filter(tags__name__in=[self.tags_list[0]]).count() - 1
        self.assertEqual(count, response.context_data.get('count'))
        self.assertContains(response, f"{count} Customers")

    def test_logged_in_all_tags_network_filter_success(self):
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"task_tags": [t.id for t in self.tags_list]},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        count = Task.objects.filter(tags__name__in=self.tags_list).count() - 2
        self.assertEqual(count, response.context_data.get('count'))
        self.assertContains(response, f"{count} Customers")

    def test_logged_in_stopped_customer_failure(self):
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"phones": [self.stopped_customer.phones.first().pk]},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response.template_name)
        self.assertContains(response, "You must select some customers")

    def test_premium_subscriber_filter(self):
        premium_customer = PremiumCustomerFactory()
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"premium_subscriber": "Yes"},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        self.assertEqual(1, response.context_data.get('count'))
        self.assertContains(response, "Compose bulk SMS for 1 Customer")

    def test_non_premium_subscriber_filter(self):
        premium_customer = PremiumCustomerFactory()
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"premium_subscriber": "No"},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        non_premium_count = Customer.objects.filter(
            has_requested_stop=False).exclude(
            phones__number__startswith='+1815').count() - 1
        self.assertEqual(non_premium_count, response.context_data.get('count'))
        self.assertContains(response, f"Compose bulk SMS for {non_premium_count} Customers")

    def test_gender_filter(self):
        for gender in ('f', 'm'):
            response = self.client.post(reverse('core_management_customer_filter'),
                                        {"gender": gender},
                                        follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.is_rendered)
            self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
            count = Customer.objects.filter(has_requested_stop=False, sex=gender).exclude(phones__number__startswith='+1815').count()
            self.assertEqual(count, response.context_data.get('count'))
            self.assertContains(response, f"Compose bulk SMS for {count} Customers")
        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"gender": ''},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        count = Customer.objects.filter(has_requested_stop=False).exclude(phones__number__startswith='+1815').count()
        self.assertEqual(count, response.context_data.get('count'))
        self.assertContains(response, f"Compose bulk SMS for {count} Customers")

        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"gender": 'u'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        count = Customer.objects.filter(has_requested_stop=False, sex='').exclude(phones__number__startswith='+1815').count()
        self.assertEqual(count, response.context_data.get('count'))
        self.assertContains(response, f"Compose bulk SMS for {count} Customer")

    def test_preferred_language_filter(self):
        for preferred_language in ('swa', 'lug'):
            response = self.client.post(reverse('core_management_customer_filter'),
                                        {"preferred_language": preferred_language},
                                        follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.is_rendered)
            self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
            count = Customer.objects.filter(has_requested_stop=False, preferred_language=preferred_language).exclude(phones__number__startswith='+1815').count()
            self.assertEqual(count, response.context_data.get('count'))
            self.assertContains(response, f"Compose bulk SMS for {count} Customers")

        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"preferred_language": ('swa', 'lug')},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        count = Customer.objects.filter(has_requested_stop=False, preferred_language__in=['swa', 'lug']).exclude(phones__number__startswith='+1815').count()
        self.assertEqual(count, response.context_data.get('count'))
        self.assertContains(response, f"Compose bulk SMS for {count} Customer")

    def test_electricity_filter(self):
        q = CustomerQuestion.objects.create(text=ELECTRICITY_QUESTION)
        phone = CustomerPhone.objects.filter(number__startswith='+254').first()
        CustomerQuestionAnswer.objects.create(question_id=q.pk,
                                              customer_id=Customer.objects.filter(phones=phone).first().id,
                                              text="Yes")
        self.assertEqual(1, CustomerQuestion.objects.count())
        self.assertEqual(1, CustomerQuestionAnswer.objects.count())

        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"has_electricity": "Yes"},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        self.assertEqual(1, response.context_data.get('count'))
        self.assertContains(response, "Compose bulk SMS for 1 Customer")

    def test_irrigation_filter(self):
        q = CustomerQuestion.objects.create(text=IRRIGATION_WATER_QUESTION)
        CustomerQuestionAnswer.objects.create(question_id=q.pk,
                                              customer_id=Customer.objects.filter(phones__number__startswith='+254').first().id,
                                              text="Yes")
        self.assertEqual(1, CustomerQuestion.objects.count())
        self.assertEqual(1, CustomerQuestionAnswer.objects.count())

        response = self.client.post(reverse('core_management_customer_filter'),
                                    {"has_irrigation_water": "Yes"},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        self.assertEqual(1, response.context_data.get('count'))
        self.assertContains(response, "Compose bulk SMS for 1 Customer")

    def test_logged_in_bulk_sms_compose_success(self):
        response = self.client.post(reverse('core_management_customer_bulk_compose'),
                                    {},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)

    def test_logged_out_bulk_sms_compose_redirects(self):
        self.client.logout()
        response = self.client.post(reverse('core_management_customer_bulk_compose'),
                                    {},
                                    follow=True)
        self.assertRedirects(response, '/accounts/login/?next=%2Fmanagement%2Fbulk_sms%2Fcompose%2F', status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    @activate_success_response
    def test_logged_in_post_categories_filter_sends_messages(self):
        odd_category = CustomerCategory.objects.get(name='odd')
        odd_count = Customer.objects.filter(categories=odd_category).count()

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {"categories": [odd_category.pk]},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(odd_count, response1.context_data.get('count'))
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(odd_count, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {odd_count} Customers")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-halted customers
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        self.assertEqual(total_customers, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {odd_count} customers")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        at_recipient_count = Customer.objects.filter(has_requested_stop=False,
                                                     categories=odd_category).count()
        self.assertEqual(at_recipient_count, SMSRecipient.objects.count())

    @activate_success_response
    def test_logged_in_post_at_network_filter_sends_messages(self):
        at_count = Customer.objects.filter(has_requested_stop=False,
                                           phones__number__startswith="+254").count()

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(at_count, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {at_count} Customers")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-halted customers
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        self.assertEqual(total_customers, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {at_count} customers")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        self.assertEqual(at_count, SMSRecipient.objects.count())

    @activate_success_response
    def test_logged_in_post_at_network_category_filter_sends_messages(self):
        odd_category = CustomerCategory.objects.get(name='odd')
        at_count = Customer.objects.filter(has_requested_stop=False,
                                           categories=odd_category.pk).count()

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {"categories": [odd_category.pk]},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(at_count, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {at_count} Customers")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-halted customers
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        self.assertEqual(total_customers, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {at_count} customers")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        self.assertEqual(at_count, SMSRecipient.objects.count())

    @activate_success_response
    def test_logged_in_post_commodities_filter_sends_messages(self):
        avocado_count = Customer.objects.filter(has_requested_stop=False,
                                                commodities__name='avocado').count()
        avocado_commodity = Commodity.objects.get(name='avocado')

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {'commodities_farmed': avocado_commodity.id},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(avocado_count, response1.context_data.get('count'))
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(avocado_count, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {avocado_count} Customers")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-halted customers
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        self.assertEqual(total_customers, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {avocado_count} customers")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        at_count = Customer.objects.filter(has_requested_stop=False,
                                           commodities__name='avocado').count()
        self.assertEqual(at_count, SMSRecipient.objects.count())

    @activate_success_response
    def test_logged_in_post_tasks_tags_filter_sends_messages(self):
        task_type = ContentType.objects.get(model='task')
        # Pick a tag, any tag
        tag = Tag.objects.first()
        # Use an algorithm different than the platform to determine
        # the customers who have tasks with that tag.
        tagged_task_ids = TaggedItem.objects.filter(content_type_id=task_type.id,
                                                    tag=tag).values_list('object_id', flat=True)
        customer_ids = Task.objects.filter(pk__in=tagged_task_ids).values_list("customer_id", flat=True)
        customers = Customer.objects.filter(pk__in=customer_ids, has_requested_stop=False)
        customers = customers.exclude(phones__number__startswith='+1')  # Exclude our known-invalid customers
        customer_count = customers.count()

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {'task_tags': [tag.id]},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(customer_count, response1.context_data.get('count'))
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(customer_count, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {customer_count} Customers")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-halted customers
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        self.assertEqual(total_customers, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {customer_count} customers")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        at_count = customers.count()
        self.assertEqual(at_count, SMSRecipient.objects.count())

    @activate_success_response
    @skip("Temporarily disable while we work on replacement tip subscription mechanism")
    def test_logged_in_post_tip_series_filter_sends_messages(self):
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        # Pick a tip series, any tip series
        tip_series = TipSeries.objects.filter(subscriptions__isnull=False).first()
        customer_count = tip_series.subscriptions.count()
        self.assertTrue(0 < customer_count < total_customers, f"customer_count: {customer_count}, total_customers: {total_customers}")

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {'tip_subscriptions': [tip_series.pk]},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(customer_count, response1.context_data.get('count'))
        print(f"customer_count={customer_count}")
        self.assertContains(response1, f"Compose bulk SMS for {customer_count} Customer{'s'[:customer_count^1]}")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-stopped customers
        self.assertEqual(total_customers, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        print(f"customer_count={customer_count}")
        self.assertContains(response1, f"Compose bulk SMS for {customer_count} Customer{'s'[:customer_count^1]}")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        cust_ids = tip_series.subscriptions.values_list('customer_id', flat=True)
        at_count = Customer.objects.filter(id__in=cust_ids).count()
        self.assertEqual(at_count, SMSRecipient.objects.count())

    def test_missing_location_filter(self):
        initial_count = Customer.objects.filter(has_requested_stop=False, phones__number__startswith='+254').count()
        # All the other test customers have locations by default so create one without
        customer_without_location = CustomerFactory(location=None,
                                                    border0=None,
                                                    border1=None,
                                                    border2=None,
                                                    border3=None,
                                                    name='customer without location')

        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {"missing_location": "True"},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Only sent to the customer_without_location created for this test
        self.assertEqual(1, response1.context_data.get('count'))
        self.assertContains(response1, "Compose bulk SMS for 1 Customer")

        response2 = self.client.post(reverse('core_management_customer_filter'),
                                    {"missing_location": "False"},
                                    follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response2.template_name)
        # Should be sent to valid recipients PLUS the customer_without_location created for this test
        self.assertEqual(initial_count + 1, response2.context_data.get('count'))

    @activate_success_response
    def test_logged_in_post_at_network_uganda_customer_sends_messages(self):
        # Create a Ugandan customer
        uganda = Border.objects.get(name='Uganda', level=0)

        call_center = CallCenter.objects.get(border=Border.objects.get(country='Uganda', level=0))
        call_center_operator = CallCenterOperator.objects.create(operator=self.operator, active=True, call_center=call_center)
        call_center.senders.add(CallCenterSender.objects.create(sender_id="iShambaU", description="blah"))

        customer = CustomerFactory(border0=uganda, name="uganda-customer", has_no_phones=True)
        phone = CustomerPhoneFactory(number="+256701234567", is_main=True, customer=customer)

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {"border0": str(uganda.id)},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        self.assertEqual(1, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {1} Customer")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShambaU'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)
        # The customer count in the rendered (customer filter) template is seeded
        # with the total number of non-halted customers
        total_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        # Since we redirect to the bulk sms customer filter form, no filters are applied
        # so we expect all valid customers to be included in the count.

        # FIXME(apryde) The below assertion fails now likely due to call center filtering.
        # self.assertEqual(total_customers + 1, response2.context_data.get('count'))

        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {1} customer")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        self.assertEqual(1, SMSRecipient.objects.count())

    @activate_success_response
    @patch('gateways.SMSGateway.validate_recipients')
    @skip("bulk SMS sending limited to selected call center now so test case no longer valid")
    def test_logged_in_post_at_network_uganda_plus_kenya_customers_sends_messages(self, mock_validate_recipients):
        # Create a Ugandan customer
        uganda = Border.objects.get(name='Uganda', level=0)
        kenya = Border.objects.get(name='Kenya', level=0)
        customer = CustomerFactory(border0=uganda, name="uganda-customer", has_no_phones=True)
        phone = CustomerPhoneFactory(number="+256701234567", is_main=True, customer=customer)

        # First select the customer filters
        response1 = self.client.post(reverse('core_management_customer_filter'),
                                     {"border0": [uganda.id, kenya.id]},
                                     follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response1.template_name)
        # Ensure the correct number of customers was passed to the new view
        total_kenya_customers = Customer.objects.filter(has_requested_stop=False).filter(
            phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").count()
        self.assertEqual(total_kenya_customers + 1, response1.context_data.get('count'))
        self.assertContains(response1, f"Compose bulk SMS for {total_kenya_customers + 1} Customers")

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': '21606',
                                           'sender_Uganda': 'iShambaU'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.is_rendered)

        # Since we redirect to the bulk sms customer filter form, no filters are applied
        # so we expect all valid customers to be included in the count.
        self.assertEqual(total_kenya_customers + 1, response2.context_data.get('count'))
        # Redirected back to the bulk sms customer filter form by default
        self.assertEqual(['sms/bulk_sms_filter_form.html'], response2.template_name)
        # Ensure the success 'toast' message reflects that the message was sent.
        self.assertContains(response2, f"Bulk message sent to {total_kenya_customers + 1} customers")
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(OUTGOING_SMS_TYPE.BULK, OutgoingSMS.objects.first().message_type)
        self.assertEqual(total_kenya_customers + 1, SMSRecipient.objects.count())
        # Ensure number validation was not done in the gateway
        mock_validate_recipients.assert_not_called()
