from unittest.mock import patch
from xml.dom.minidom import parseString

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from django_tenants.test.client import TenantClient as Client

from calls.models import Call, CallCenterPhone, PusherSession
from core.test.cases import TestCase
from customers.constants import JOIN_METHODS
from customers.models import Customer
from customers.tests.factories import (CustomerFactory, PremiumCustomerFactory,
                                       SubscriptionFactory)
from gateways.africastalking.testing import activate_success_response
from sms.models import OutgoingSMS, SMSRecipient

from .util import (get_dequeue_call_data, get_hang_call_data,
                   get_hang_up_dequeue_call_data, get_make_call_data,
                   get_make_dequeue_call_data)

valid_ip = settings.AUTHORIZED_IPS[0]


class VoiceCallbackResponseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)

        self.active_customer = PremiumCustomerFactory(
            subscriptions=(SubscriptionFactory(),)
        )
        self.unregistered_customer = CustomerFactory(unregistered=True)

        self.new_customer_phone = '+254 720 123456'

        self.operator = get_user_model().objects.create(username='operator')
        self.call_center_phone_number = '+254 20 100001'
        self.call_center_phone = CallCenterPhone.objects.create(
            phone_number=self.call_center_phone_number,
            is_active=True,
        )

    def test_active_customer_call_arrival_empty_call_centre(self):
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        expected_url = 'https://tenant.fast-test.com/static/calls/audio/closed.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), expected_url)

    def test_active_customer_call_arrival_non_empty_call_centre(self):
        PusherSession.objects.create(
            call_center_phone=self.call_center_phone,
            operator=self.operator,
            pusher_session_key='11122',
        )
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Enqueue')
        # one call is now in the queue
        self.assertEqual(Call.objects.queued().filter(customer__phones__number=self.active_customer.main_phone).count(), 1)

    def test_active_customer_call_hang(self):
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        data = get_hang_call_data(data['sessionId'], self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_dequeue_call_arrival(self):
        PusherSession.objects.create(
            call_center_phone=self.call_center_phone,
            operator=self.operator,
            pusher_session_key='111',
        )
        response = self.client.post(reverse('voice_api_callback'), get_make_dequeue_call_data(self.call_center_phone.phone_number))
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Dequeue')
        self.assertEqual(dom.firstChild.firstChild.getAttribute('phoneNumber'), '+254123456780')

    def test_dequeue_call_hung_up(self):
        PusherSession.objects.create(
            call_center_phone=self.call_center_phone,
            operator=self.operator,
            pusher_session_key='11122',
        )
        response = self.client.post(reverse('voice_api_callback'), get_make_dequeue_call_data(self.call_center_phone.phone_number))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('voice_api_callback'), get_hang_up_dequeue_call_data(self.call_center_phone))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    @override_settings(MUTE_SMS=True)
    @patch('customers.managers.client_setting')
    def test_new_customer_call_arrival_restricted_call_center(self, mocked_client_setting):
        mocked_client_setting.return_value = True  # Restricted call center (only accept registered customers)
        data = get_make_call_data(caller_number=self.new_customer_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        expected_url = 'https://tenant.fast-test.com/static/calls/audio/inactive.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), expected_url)
        # Make sure the 'JOIN' SMS was NOT sent
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        c = Customer.objects.get(phones__number=self.new_customer_phone)
        self.assertEqual(JOIN_METHODS.CALL, c.join_method)
        self.assertEqual('Kenya', c.border0.name)  # Ensure the country of new customers gets set
        # Do it another time after customer has been created
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        second_expected_url = 'https://tenant.fast-test.com/static/calls/audio/inactive.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), second_expected_url)
        # Make sure we didn't send a second 'JOIN' SMS
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())
        c = Customer.objects.get(phones__number=self.new_customer_phone)
        self.assertEqual(JOIN_METHODS.CALL.value, c.join_method)
        self.assertEqual('Kenya', c.border0.name)  # Ensure the country of new customers gets set

    @override_settings(MUTE_SMS=True)
    @patch('customers.managers.client_setting')
    @activate_success_response
    def test_new_customer_call_arrival_unrestricted_call_center(self, mocked_client_setting):
        mocked_client_setting.return_value = False  # Unrestricted call center (accept all calls)
        data = get_make_call_data(caller_number=self.new_customer_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        # No registered call center agents, so the 'closed' response is played
        expected_url = 'https://tenant.fast-test.com/static/calls/audio/closed.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), expected_url)
        # Make sure the 'JOIN' SMS was sent
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, OutgoingSMS.objects.first().recipients.count())
        c = Customer.objects.get(phones__number=self.new_customer_phone)
        self.assertEqual(JOIN_METHODS.CALL, c.join_method)
        self.assertEqual('Kenya', c.border0.name)  # Ensure the country of new customers gets set
        # Do it another time after customer has been created
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        # No registered call center agents, so the 'closed' response is played
        second_expected_url = 'https://tenant.fast-test.com/static/calls/audio/closed.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), second_expected_url)
        # Make sure we didn't send a second 'JOIN' SMS
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, OutgoingSMS.objects.first().recipients.count())
        c = Customer.objects.get(phones__number=self.new_customer_phone)
        self.assertEqual(JOIN_METHODS.CALL, c.join_method)
        self.assertEqual('Kenya', c.border0.name)  # Ensure the country of new customers gets set

    @override_settings(MUTE_SMS=True)
    def test_new_customer_call_saved(self):
        self.assertRaises(Customer.DoesNotExist,
                          Customer.objects.get,
                          phones__number=self.new_customer_phone)
        self.assertRaises(Call.DoesNotExist,
                          Call.objects.get,
                          caller_number=self.new_customer_phone,
                          is_active=True)
        data = get_make_call_data(caller_number=self.new_customer_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        try:
            c = Customer.objects.get(phones__number=self.new_customer_phone)
            self.assertEqual(JOIN_METHODS.CALL, c.join_method)
            self.assertEqual('Kenya', c.border0.name)  # Ensure the country of new customers gets set
        except Customer.DoesNotExist:
            self.fail('New customer was not created')
        try:
            Call.objects.get(caller_number=self.new_customer_phone, is_active=True)
        except Call.DoesNotExist:
            self.fail('New customer call record was not saved')

    @override_settings(MUTE_SMS=True)
    @patch('customers.managers.client_setting')
    @activate_success_response
    def test_can_edit_new_customer_immediately_upon_incoming_call(self, mocked_client_setting):
        mocked_client_setting.return_value = False  # Unrestricted call center (accept all calls)
        self.assertRaises(Customer.DoesNotExist,
                          Customer.objects.get,
                          phones__number=self.new_customer_phone)
        self.assertRaises(Call.DoesNotExist,
                          Call.objects.get,
                          caller_number=self.new_customer_phone,
                          is_active=True)
        data = get_make_call_data(caller_number=self.new_customer_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        # An SMS is sent to new customers, asking them to initiate a USSD to complete their registration
        self.assertEqual(1, OutgoingSMS.objects.count())
        self.assertEqual(1, SMSRecipient.objects.count())
        try:
            c = Customer.objects.get(phones__number=self.new_customer_phone)
            self.assertEqual(JOIN_METHODS.CALL, c.join_method)
            data = {
                'name': 'Mr John Doe',
                'phone': self.new_customer_phone,
                'village': 'somewhere',
                'location': '{"type":"Point","coordinates":[36.863250732421875,-1.2729360401038594]}',
                'is_registered': True,
                'preferred_language': 'eng',
                'market_subscriptions-TOTAL_FORMS': '2',
                'market_subscriptions-INITIAL_FORMS': '0',
                'market_subscriptions-MIN_NUM_FORMS': '0',
                'market_subscriptions-MAX_NUM_FORMS': '1000',
                'answers-TOTAL_FORMS': '0',
                'answers-INITIAL_FORMS': '0',
                'answers-MIN_NUM_FORMS': '0',
                'answers-MAX_NUM_FORMS': '1000',
            }
            response = self.client.post(
                reverse('customers:customer_update', kwargs={'pk': c.pk}),
                data=data,
                follow=True
            )
            self.assertEqual(200, response.status_code)
            # No new messages should be sent as a result of the customer edit.
            self.assertEqual(1, OutgoingSMS.objects.count())
            self.assertEqual(1, SMSRecipient.objects.count())
            self.assertEqual(0, len(response.context['messages']))
        except Customer.DoesNotExist:
            self.fail('New customer was not created')
        try:
            Call.objects.get(caller_number=self.new_customer_phone, is_active=True)
        except Call.DoesNotExist:
            self.fail('New customer call record was not saved')

    @override_settings(MUTE_SMS=True)
    def test_new_customer_hangs_up_unanswered(self):
        data = get_make_call_data(caller_number=self.new_customer_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        # Now the customer hangs up
        data = get_hang_call_data(data['sessionId'], self.new_customer_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 1)
        call = all_calls[0]
        self.assertFalse(call.is_active)
        self.assertFalse(call.connected)
        self.assertEqual(call.customer.format_phone_number(), self.new_customer_phone)
        self.assertEqual(call.destination_number, '+254123456780')
        self.assertEqual(call.duration, data['durationInSeconds'])
        self.assertEqual(call.cost, data['amount'])
        c = Customer.objects.get(phones__number=self.new_customer_phone)
        self.assertEqual(JOIN_METHODS.CALL, c.join_method)
        self.assertEqual('Kenya', c.border0.name)  # Ensure the country of new customers gets set

    @patch('customers.managers.client_setting')
    def test_inactive_customer_call_arrival_restricted_call_center(self, mocked_client_setting):
        mocked_client_setting.return_value = True  # Unrestricted call center (only accept registered customers)
        data = get_make_call_data(caller_number=self.unregistered_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        expected_url = 'https://tenant.fast-test.com/static/calls/audio/inactive.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), expected_url)
        # Make sure a 'JOIN' SMS was NOT sent.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    @patch('customers.managers.client_setting')
    def test_inactive_customer_call_arrival_unrestricted_call_center(self, mocked_client_setting):
        mocked_client_setting.return_value = False  # Unrestricted call center (accept all calls)
        data = get_make_call_data(caller_number=self.unregistered_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Play')
        self.assertTrue(dom.firstChild.firstChild.hasAttribute('url'))
        # No registered call center agents, so the 'closed' response is played
        expected_url = 'https://tenant.fast-test.com/static/calls/audio/closed.mp3'
        self.assertEqual(dom.firstChild.firstChild.getAttribute('url'), expected_url)
        # Make sure a 'JOIN' SMS was NOT sent. I.e. if the customer already existed,
        # despite being in unregistered status, a new 'JOIN' SMS message should not be sent.
        self.assertEqual(0, OutgoingSMS.objects.count())
        self.assertEqual(0, SMSRecipient.objects.count())

    def test_inactive_customer_call_saved(self):
        self.assertRaises(Call.DoesNotExist,
                          Call.objects.get,
                          caller_number=self.unregistered_customer.main_phone,
                          is_active=True)
        data = get_make_call_data(caller_number=self.unregistered_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        try:
            Call.objects.get(caller_number=self.unregistered_customer.main_phone, is_active=True)
        except Call.DoesNotExist:
            self.fail('Inactive customer call record was not saved')

    def test_inactive_customer_hangs_up_unanswered(self):
        data = get_make_call_data(caller_number=self.unregistered_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        # Now the customer hangs up
        data = get_hang_call_data(data['sessionId'], self.unregistered_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 1)
        call = all_calls[0]
        self.assertFalse(call.is_active)
        self.assertFalse(call.connected)
        self.assertEqual(call.customer.format_phone_number(), self.unregistered_customer.main_phone)
        self.assertEqual(call.destination_number, '+254123456780')
        self.assertEqual(call.duration, data['durationInSeconds'])
        self.assertEqual(call.cost, data['amount'])


class VoiceCallbackActionsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)

        self.active_customer = PremiumCustomerFactory(
            subscriptions=(SubscriptionFactory(),)
        )

        self.operator = get_user_model().objects.create(username='operator')
        self.call_center_phone_number = '+254 20 100001'
        self.call_center_phone = CallCenterPhone.objects.create(
            phone_number=self.call_center_phone_number,
            is_active=True,
        )

    def test_active_customer_call_arrival(self):
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 1)
        self.assertEqual(Call.objects.queued().filter(customer__phones__number=self.active_customer.main_phone).count(), 1)
        call = all_calls[0]
        self.assertTrue(call.is_active)
        self.assertFalse(call.connected)
        self.assertEqual(call.customer, self.active_customer)
        self.assertEqual(call.destination_number, '+254123456780')
        self.assertEqual(call.duration, None)
        self.assertEqual(call.cost, None)

    def test_active_customer_call_hang(self):
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        data = get_hang_call_data(data['sessionId'], data['callerNumber'])
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 1)
        call = all_calls[0]
        self.assertFalse(call.is_active)
        self.assertFalse(call.connected)
        self.assertEqual(call.customer, self.active_customer)
        self.assertEqual(call.destination_number, '+254123456780')
        self.assertEqual(call.duration, data['durationInSeconds'])
        self.assertEqual(call.cost, data['amount'])

    def test_dequeue_active_customer(self):
        pusher_session = PusherSession.objects.create(
            call_center_phone=self.call_center_phone,
            operator=self.operator,
            pusher_session_key='111',
        )

        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 1)
        call = all_calls[0]
        self.assertTrue(call.is_active)
        self.assertFalse(call.connected)
        self.assertEqual(Call.objects.queued().count(), 1)

        data2 = get_make_dequeue_call_data(self.call_center_phone.phone_number)
        response = self.client.post(reverse('voice_api_callback'), data2)
        pusher_session = PusherSession.objects.get(pk=pusher_session.pk)
        self.assertEqual(pusher_session.provided_call_id, data2['sessionId'])

        data3 = get_dequeue_call_data(data['sessionId'], data['callerNumber'], data2['sessionId'])
        response = self.client.post(reverse('voice_api_callback'), data3)
        self.assertEqual(response.status_code, 200)
        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 1)
        call = all_calls[0]
        self.assertTrue(call.is_active)
        self.assertTrue(call.connected)
        self.assertEqual(call.cco, self.operator)
        self.assertEqual(Call.objects.queued().count(), 0)

    def test_active_customer_duplicate_call_arrival(self):
        PusherSession.objects.create(
            call_center_phone=self.call_center_phone,
            operator=self.operator,
            pusher_session_key='111',
        )

        data1 = get_make_call_data(caller_number=self.active_customer.main_phone)
        self.client.post(reverse('voice_api_callback'), data1)
        # repeat
        data2 = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = self.client.post(reverse('voice_api_callback'), data2)
        self.assertEqual(response.status_code, 200)

        all_calls = Call.objects.all()
        self.assertEqual(all_calls.count(), 2)
        first_call = all_calls.get(provided_id=data1['sessionId'])
        second_call = all_calls.get(provided_id=data2['sessionId'])

        # second call should have been enqueued
        self.assertNotEqual(response.content, b'')
        dom = parseString(response.content)
        self.assertEqual(dom.firstChild.localName, 'Response')
        self.assertEqual(dom.firstChild.firstChild.localName, 'Enqueue')

        # first call should have been marked inactive
        self.assertFalse(first_call.is_active)
        self.assertFalse(first_call.connected)
        # second call should now be in the queue
        self.assertTrue(second_call.is_active)
        self.assertFalse(second_call.connected)
        self.assertEqual(Call.objects.queued().count(), 1)
        self.assertEqual(Call.objects.queued().get(), second_call)


class VoiceCallbackFirewallTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.active_customer = PremiumCustomerFactory(
            subscriptions=(SubscriptionFactory(),)
        )

        self.good_ip = valid_ip
        self.bad_ip = '9.9.9.9'

    def test_good_ip_call_arrival(self):
        c = Client(self.tenant, REMOTE_ADDR=self.good_ip)
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = c.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 200)

    def test_bad_ip_call_arrival(self):
        c = Client(self.tenant, REMOTE_ADDR=self.bad_ip)
        data = get_make_call_data(caller_number=self.active_customer.main_phone)
        response = c.post(reverse('voice_api_callback'), data)
        self.assertEqual(response.status_code, 403)
