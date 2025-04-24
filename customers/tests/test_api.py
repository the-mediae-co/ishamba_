import json
from unittest import skip
from unittest.mock import patch

from django.urls import reverse
from customers.constants import JOIN_METHODS

from gateways.africastalking.testing import activate_success_response
from rest_framework.test import APIRequestFactory

from core.test.cases import TestCase

from sms.models import OutgoingSMS
from tasks.models import Task
from world.models import Border

from customers.apiv1.views import CustomerJoinView
from ..models import Customer, CustomerPhone
from .factories import CustomerFactory


class CustomersApiTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.whitelisted_ip = '46.43.3.10'
        self.non_whitelisted_ip = '8.8.8.8'
        self.factory = APIRequestFactory(REMOTE_ADDR=self.whitelisted_ip)
        self.data = {'phone': '+254722100200', 'name': 'goober'}
        self.join_url = reverse('apiv1:customers:join')

    @skip("We're now allowing any IP as the request on ishamba.com is done on the frontend")
    def test_unwhitelisted_ip_raises_Http403(self):
        factory = APIRequestFactory(REMOTE_ADDR=self.non_whitelisted_ip)
        request = factory.post(self.join_url, self.data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)
        self.assertEqual(response.status_code, 403)

    @activate_success_response
    def test_whitelisted_ip_creates_customer(self):
        # precondition
        self.assertEqual(Customer.objects.count(), 0)

        request = self.factory.post(self.join_url, self.data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Customer.objects.count(), 1)

    @activate_success_response
    def test_missing_phone_rejects_customer(self):
        # precondition
        self.assertEqual(Customer.objects.count(), 0)
        data = {'name': 'goober'}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(400, response.status_code)
        self.assertTrue('phone' in response.data)
        self.assertTrue(response.exception)
        self.assertEqual(Customer.objects.count(), 0)

    @activate_success_response
    def test_missing_name_accepts_customer(self):
        # precondition
        self.assertEqual(0, Customer.objects.count())
        phone = '+254722100200'
        data = {'phone': phone}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(201, response.status_code)
        self.assertEqual(1, Customer.objects.count())

        phone = CustomerPhone.objects.get(number=phone)
        c = phone.customer
        self.assertEqual(JOIN_METHODS.WEB, c.join_method)
        self.assertEqual(Border.objects.get(country='Kenya', level=0), c.border0)

    @activate_success_response
    @patch('customers.models.Customer.enroll')
    def test_uganda_phone_accepts_customer(self, mocked_enroll):
        # precondition
        self.assertEqual(0, Customer.objects.count())
        phone = '+256720000000'
        data = {'phone': phone}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(201, response.status_code)
        self.assertEqual(1, Customer.objects.count())
        # We have to mock the enroll() method to prevent errors in sending a welcome message to Uganda
        mocked_enroll.assert_called()

        phone = CustomerPhone.objects.get(number=phone)
        c = phone.customer
        self.assertEqual(JOIN_METHODS.WEB, c.join_method)
        self.assertEqual(Border.objects.get(country='Uganda', level=0), c.border0)

    @activate_success_response
    @patch('customers.models.Customer.enroll')
    def test_usa_phone_rejects_customer(self, mocked_enroll):
        # Trying to join from a country where we do not operate should not create a customer

        # precondition
        self.assertEqual(0, Customer.objects.count())
        phone = '+18156750501'
        data = {'phone': phone}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(400, response.status_code)
        self.assertTrue('phone' in response.data)
        self.assertTrue(response.exception)
        self.assertEqual(0, Customer.objects.count())
        # We have to mock the enroll() method to prevent errors in sending a welcome message to Uganda
        mocked_enroll.assert_not_called()

    @activate_success_response
    @patch('customers.models.Customer.enroll')
    def test_long_name_rejects_customer(self, mocked_enroll):
        # Trying to join with a name longer than our field allows

        # precondition
        self.assertEqual(0, Customer.objects.count())
        phone = '+256720000000'
        # field validation has max of 120, this is 121 chars long
        name = '0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890'
        self.assertGreater(len(name), 120)
        data = {'phone': phone, 'name': name}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(400, response.status_code)
        self.assertTrue('name' in response.data)
        self.assertTrue(response.exception)
        self.assertEqual(0, Customer.objects.count())
        # We have to mock the enroll() method to prevent errors in sending a welcome message to Uganda
        mocked_enroll.assert_not_called()

    @activate_success_response
    @patch('customers.models.Customer.enroll')
    def test_long_phone_rejects_customer(self, mocked_enroll):
        # Trying to join with a phone longer than our field allows

        # precondition
        self.assertEqual(0, Customer.objects.count())
        # field validation has max of 50, this is 51 chars long
        phone = '+25672678901234567890123456789012345678901234567890'
        self.assertGreater(len(phone), 50)
        name = 'goober'
        data = {'phone': phone, 'name': name}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(400, response.status_code)
        self.assertTrue('phone' in response.data)
        self.assertTrue(response.exception)
        self.assertEqual(0, Customer.objects.count())
        # We have to mock the enroll() method to prevent errors in sending a welcome message to Uganda
        mocked_enroll.assert_not_called()

    @activate_success_response
    def test_extra_data_accepts_customer_without_extra_data(self):
        # precondition
        self.assertEqual(0, Customer.objects.count())
        data = {'phone': '+254720123456',
                'name': 'goober',
                'malicious': 'injection',
                'id_number': '1234456789',
                'village': 'malicious_village'}

        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        self.assertEqual(201, response.status_code)
        self.assertEqual(1, Customer.objects.count())
        self.assertFalse(response.exception)
        # Ensure that the malicious key injection did not make it into the customer instance
        c = Customer.objects.first()
        self.assertFalse('malicious' in dir(c))
        self.assertNotEqual(data['id_number'], c.id_number)
        self.assertNotEqual(data['village'], c.village)

    @activate_success_response
    def test_whitelisted_ip_join_api_sends_sms_and_does_not_create_task(self):
        self.assertEqual(Task.objects.count(), 0)
        request = self.factory.post(self.join_url, self.data)
        join_view = CustomerJoinView.as_view()
        join_view(request)

        sms = OutgoingSMS.objects.first()
        customer = Customer.objects.first()
        smsr = sms.recipients.first()
        self.assertEqual(smsr.recipient, customer)
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(JOIN_METHODS.WEB, customer.join_method)

    @activate_success_response
    def test_whitelisted_ip_existing_customer_400_bad_request(self):
        customer = CustomerFactory()

        data = {'phone': customer.phones.first().number, 'name': customer.name}
        request = self.factory.post(self.join_url, data)
        join_view = CustomerJoinView.as_view()
        response = join_view(request)

        # Ensure we get 400 Bad Request response as one can't add existing Customers
        self.assertEqual(response.status_code, 400)

        expected = {'phone': ['That phone number is already used by an existing customer.']}
        content = json.loads(response.render().content)

        # Ensure we tell the client why they're getting a 400 Bad Request
        self.assertEqual(
            dict(content, **expected),
            content,
        )
        self.assertNotEqual(JOIN_METHODS.WEB, customer.join_method)
