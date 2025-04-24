import logging
import datetime
from unittest.mock import patch

from django.urls import reverse
from django.test import override_settings
from django.utils import timezone
from customers.constants import STOP_METHODS

from gateways.africastalking.views import ATDeliveryReportView, ATIncomingSMSView
from sms.models import SMSRecipient, IncomingSMS

from sms.tests.factories import OutgoingSMSFactory
from customers.models import Customer
from customers.tests.factories import CustomerFactory

from django_tenants.test.client import TenantClient

from core.test.cases import TestCase


class ATIncomingSMSViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

    @override_settings(IP_AUTHORIZATION=False, MUTE_SMS=True)
    def test_form_accepts_valid_data(self):
        customer = CustomerFactory()
        resp = self.client.post(
            reverse('gateways:africastalking:incoming_sms'),
            data={
                'from': customer.main_phone,
                'to': '30606',
                'text': 'hello world',
                'date': '2016-06-17T13:56:03Z',
                'id': 'foo-bar-id',
            }
        )
        self.assertEqual(resp.status_code, 200)
        # Make sure the country gets set on the new customer
        self.assertEqual('Kenya', Customer.objects.first().border0.name)

    @override_settings(IP_AUTHORIZATION=False)
    @patch('sms.views.sms_received.send')
    def test_at_treated_as_utc(self, sms_recieved_mock):
        dt_str = '2016-06-17T13:56:03Z'
        self.client.post(
            reverse('gateways:africastalking:incoming_sms'),
            data={
                'from': '+254700000000',
                'to': '30606',
                'text': 'hello world',
                'date': dt_str,
                'id': 'foo-bar-id',
            }
        )
        sms_recieved_mock.assert_called()
        __, kwargs = sms_recieved_mock.call_args

        msg = kwargs['instance']
        self.assertEqual(datetime.timezone.utc, msg.at.tzinfo)
        self.assertEqual(dt_str, msg.at.strftime('%Y-%m-%dT%H:%M:%SZ'))

    def test_ip_authorization_blocks_request(self):
        # disable logging as we expect log message to be emitted here
        logging.disable(logging.CRITICAL)
        resp = self.client.post(
            reverse('gateways:africastalking:incoming_sms'),
            data={
                'from': '+254700000000',
                'to': '30606',
                'text': 'hello world',
                'date': '2016-06-17T13:56:03Z',
                'id': 'foo-bar-id',
            }
        )
        logging.disable(logging.NOTSET)

        self.assertEqual(resp.status_code, 403)

    @patch('sms.signals.signals.sms_received.send')
    @override_settings(IP_AUTHORIZATION=False)
    def test_sms_received_signal_sent(self, mock_signal):
        dt_str = '2016-06-17T13:56:03Z'
        self.client.post(
            reverse('gateways:africastalking:incoming_sms'),
            data={
                'from': '+254700000000',
                'to': '30606',
                'text': 'hello world',
                'date': dt_str,
                'id': 'foo-bar-id',
            }
        )
        mock_signal.assert_called()
        _, kwargs = mock_signal.call_args
        view = kwargs['sender']
        msg = kwargs['instance']
        self.assertEqual(ATIncomingSMSView, view, "Wrong signal sender")
        self.assertIsInstance(msg, IncomingSMS, "Wrong message instance")
        self.assertEqual(datetime.timezone.utc, msg.at.tzinfo)
        self.assertEqual(dt_str, msg.at.strftime('%Y-%m-%dT%H:%M:%SZ'))

    @override_settings(IP_AUTHORIZATION=False)
    @patch('sms.views.sms_received.send')
    def test_form_accepts_ETA_data(self, sms_recieved_mock):
        dt_str = '2016-06-17T13:56:03Z'
        self.client.post(
            reverse('gateways:africastalking:incoming_sms'),
            data={
                'from': '+254700000000',
                'to': '30606',
                'text': 'hello world',
                'date': dt_str,
                'id': 'foo-bar-id',
            }
        )
        sms_recieved_mock.assert_called()
        __, kwargs = sms_recieved_mock.call_args

        view = kwargs['sender']
        msg = kwargs['instance']
        self.assertEqual(ATIncomingSMSView, view, "Wrong signal sender")
        self.assertIsInstance(msg, IncomingSMS, "Wrong message instance")
        self.assertEqual(datetime.timezone.utc, msg.at.tzinfo)
        self.assertEqual(msg.at.strftime('%Y-%m-%dT%H:%M:%SZ'), dt_str)


class ATDeliveryReportViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

    def test_delivery_report_blocks_unauthorized_ip(self):
        # disable logging as we expect log message to be emitted here
        logging.disable(logging.CRITICAL)
        resp = self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'gateway_msg_id': 'foo-bar-baz',
                'status': 'Success',
            }
        )
        logging.disable(logging.NOTSET)

        self.assertEqual(resp.status_code, 403)

    @patch('gateways.signals.delivery_report_received.send')
    @override_settings(IP_AUTHORIZATION=False)
    def test_sms_received_signal_sent(self, mock_signal):
        self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'id': 'foo-bar-baz',
                'status': 'Success',
            }
        )

        mock_signal.assert_called_with(sender=ATDeliveryReportView,
                                       mno_message_id='foo-bar-baz',
                                       status='Success',
                                       failure_reason='')

    @override_settings(IP_AUTHORIZATION=False)
    def test_update_status_receiver_updates_status(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()
        smsr = SMSRecipient.objects.create(recipient=customer,
                                           message=outgoing_sms,
                                           gateway_msg_id='foo-bar-baz')

        resp = self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'id': 'foo-bar-baz',
                'status': 'Success',
            }
        )
        self.assertEqual(resp.status_code, 200)

        smsr.refresh_from_db()
        self.assertIn(smsr.delivery_status, SMSRecipient.SUCCEEDED_STATUSES)

    @override_settings(IP_AUTHORIZATION=False)
    def test_update_status_receiver_updates_status_with_failure_reason(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()
        smsr = SMSRecipient.objects.create(recipient=customer,
                                           message=outgoing_sms,
                                           gateway_msg_id='foo-bar-baz')

        resp = self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'id': 'foo-bar-baz',
                'status': 'Failed',
                'failureReason': 'UserDoesNotExist'
            }
        )
        self.assertEqual(resp.status_code, 200)

        smsr.refresh_from_db()
        self.assertIn(smsr.delivery_status, SMSRecipient.FAILED_STATUSES)

    @override_settings(IP_AUTHORIZATION=False)
    def test_set_customer_stop_on_status_if_user_in_blacklist_failure_reason(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()
        smsr = SMSRecipient.objects.create(recipient=customer,
                                           message=outgoing_sms,
                                           gateway_msg_id='foo-bar-baz')
        self.assertEqual(False, customer.has_requested_stop)

        resp = self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'id': 'foo-bar-baz',
                'status': 'Failed',
                'failureReason': 'UserInBlackList'
            }
        )
        self.assertEqual(resp.status_code, 200)

        smsr.refresh_from_db()
        self.assertIn(smsr.delivery_status, SMSRecipient.FAILED_STATUSES)
        customer.refresh_from_db()
        self.assertEqual(True, customer.has_requested_stop)
        self.assertEqual(STOP_METHODS.BLACKLIST, customer.stop_method)
        self.assertEqual(timezone.now().date(), customer.stop_date)

    @override_settings(IP_AUTHORIZATION=False)
    def test_set_customer_stop_on_status_if_user_has_unsupported_number_type(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()
        smsr = SMSRecipient.objects.create(recipient=customer,
                                           message=outgoing_sms,
                                           gateway_msg_id='foo-bar-baz')
        self.assertFalse(customer.has_requested_stop)

        resp = self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'id': 'foo-bar-baz',
                'status': 'Failed',
                'failureReason': 'UnsupportedNumberType'
            }
        )
        self.assertEqual(resp.status_code, 200)

        smsr.refresh_from_db()
        self.assertIn(smsr.delivery_status, SMSRecipient.FAILED_STATUSES)
        customer.refresh_from_db()
        self.assertTrue(customer.has_requested_stop)
        self.assertEqual(STOP_METHODS.INVALID, customer.stop_method)
        self.assertEqual(timezone.now().date(), customer.stop_date)

    @patch('gateways.signals.delivery_report_received.send')
    @override_settings(IP_AUTHORIZATION=False)
    def test_sms_received_signal_when_no_mno_message_id(self, mock_signal):
        self.client.post(
            reverse('gateways:africastalking:delivery_report'),
            data={
                'status': 'Success',
            }
        )

        mock_signal.assert_called_with(sender=ATDeliveryReportView,
                                       mno_message_id='',
                                       status='Success',
                                       failure_reason='')

    @override_settings(IP_AUTHORIZATION=False)
    def test_update_status_receiver_accepts_missing_mno_message_id(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()
        smsr = SMSRecipient.objects.create(recipient=customer,
                                           message=outgoing_sms,)

        with self.assertLogs('sms.signals.handlers', level='ERROR') as logs:
            resp = self.client.post(
                reverse('gateways:africastalking:delivery_report'),
                data={'status': 'Success',}
            )

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(logs.output, ['ERROR:sms.signals.handlers:Invalid delivery report received'])

        smsr.refresh_from_db()
        self.assertIn(smsr.delivery_status, SMSRecipient.PENDING_STATUSES)
        self.assertEqual(None, smsr.gateway_msg_id)
