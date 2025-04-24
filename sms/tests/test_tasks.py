from unittest import skip
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from django_tenants.test.client import TenantClient as Client

from core.test.cases import TestCase
from customers.models import Customer, NPSResponse
from customers.tests.factories import CustomerFactory
from gateways import gateways
from gateways.africastalking.testing import (activate_error_response,
                                             activate_success_response)
from sms import constants
from sms.models import OutgoingSMS, SMSRecipient
from sms.models.metrics import DailyOutgoingSMSSummary
from sms.tasks import (SendMessageBase, send_message, send_message_via_gateway,
                       send_nps_queries, update_dailyoutgoingsmssummary)
from sms.tests.factories import OutgoingSMSFactory
from sms.tests.utils import get_sms_data
from tasks.models import Task
from world.models import Border


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class SendMessageTestCase(TestCase):
    def test_can_instantiate_class(self):
        SendMessageBase()

    @patch('sms.tasks.gateways')
    def test_get_gateway_caches(self, mocked_gateways):
        task = SendMessageBase()
        task.get_gateway(gateways.AT)
        task.get_gateway(gateways.AT)
        mocked_gateways.get_gateway.assert_called_once_with(gateways.AT)

    def test_get_gateway_caching_with_kwargs(self):
        task = SendMessageBase()
        gateway1 = task.get_gateway(gateways.AT, alias="test")
        gateway2 = task.get_gateway(gateways.AT, alias="test1")
        gateway3 = task.get_gateway(gateways.AT)
        self.assertNotEqual(gateway1, gateway2)
        self.assertNotEqual(gateway1, gateway3)
        self.assertNotEqual(gateway2, gateway3)

    @activate_success_response
    def test_send_message_single_recipient(self):
        msg = OutgoingSMSFactory()
        customer = CustomerFactory()
        send_message_via_gateway.delay(
            msg.pk,
            [customer.pk],
            gateway_id=gateways.AT,
            sender=settings.GATEWAY_SECRETS['AT']['default']['sender']).get()

        self.assertEqual(OutgoingSMS.objects.count(), 1)

    @activate_success_response
    def test_send_message_multiple_georgraphies(self):
        msg = OutgoingSMSFactory()
        customer = CustomerFactory()
        customer2 = CustomerFactory(border0=Border.objects.get(country='Zambia', level=0), phones=None, add_main_phones=['+260950000000'])
        send_message.delay(
            msg.pk,
            [customer.pk, customer2.pk],
            sender=settings.GATEWAY_SECRETS['AT']['default']['sender']).get()

        self.assertEqual(OutgoingSMS.objects.count(), 1)
        self.assertEqual(SMSRecipient.objects.count(), 2)

    @override_settings(MUTE_SMS=False)
    @activate_error_response
    @patch('sms.tasks.send_message_via_gateway.retry')
    @skip("retries were disabled by https://github.com/the-mediae-co/ishamba/pull/863")
    def test_send_message_with_exception(self, retry_mock):
        retry_mock.side_effect = Exception('retried')

        with self.assertRaisesMessage(Exception, 'retried'):
            send_message_via_gateway.delay(
                ['+254711000000'],
                'foo bar baz',
                gateway_id=gateways.AT,
                sender=settings.GATEWAY_SECRETS['AT']['default']['sender']).get()

    @override_settings(MUTE_SMS=False)
    @activate_error_response
    @patch('sms.tasks.send_message_via_gateway.retry')
    @skip("retries were disabled by https://github.com/the-mediae-co/ishamba/pull/863")
    def test_backoff_initial_retry_delay(self, retry_mock):
        """
        Integration test to check that Celery calls backoff(0) for initial
        retry.
        """
        retry_mock.side_effect = []  # we don't actually want to retry

        msg = OutgoingSMSFactory()
        customer = CustomerFactory()

        try:
            send_message_via_gateway.delay(
                msg.pk,
                [customer.pk],
                gateway_id=gateways.AT,
                sender=settings.GATEWAY_SECRETS['AT']['default']['sender']).get()
        except StopIteration:
            # Exception raised due to the side-effect injected above. Just
            # ignore and check the mock.
            pass

        __, call_kwargs = retry_mock.call_args
        self.assertEqual(call_kwargs.get('countdown'), 60)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class NPSTestCase(TestCase):
    def setUp(self):
        super().setUp()
        valid_ip = constants.SMS_API_IPS[0]
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)

    def test_can_instantiate_class(self):
        SendMessageBase()

    @activate_success_response
    def test_messages_sent_and_recorded(self):
        num_recipients = 100
        CustomerFactory.create_batch(int(num_recipients/2), blank=True, preferred_language='eng')
        CustomerFactory.create_batch(int(num_recipients/2), blank=True, preferred_language='swa')
        msg_count = OutgoingSMS.objects.count()
        smsr_count = SMSRecipient.objects.count()
        send_nps_queries(TestCase.get_test_schema_name(), num_recipients=num_recipients)
        # eng and swa outgoing messages should have been created
        self.assertEqual(msg_count + 2, OutgoingSMS.objects.count())
        self.assertEqual(smsr_count + num_recipients, SMSRecipient.objects.filter(page_index=1).count())

    @activate_success_response
    def test_messages_sent_received_and_results_stored(self):
        num_recipients = 50
        CustomerFactory.create_batch(int(num_recipients/2), blank=True, preferred_language='eng')
        CustomerFactory.create_batch(int(num_recipients/2), blank=True, preferred_language='swa')
        msg_count = OutgoingSMS.objects.count()
        smsr_count = SMSRecipient.objects.count()
        # Send NPS messages to each customer
        send_nps_queries(TestCase.get_test_schema_name(), num_recipients=num_recipients)
        # eng and swa outgoing messages should have been created
        self.assertEqual(msg_count + 2, OutgoingSMS.objects.count())
        self.assertEqual(smsr_count + num_recipients, SMSRecipient.objects.filter(page_index=1).count())

        # Then have each customer send a response SMS with valid data, and confirm that they get stored
        for i, c in enumerate(Customer.objects.all()):
            from_phone = c.main_phone
            response_text = str(i % 11)
            data = get_sms_data(response_text, from_phone, '123456')
            response = self.client.post(reverse('sms_api_callback'), data)
            self.assertEqual(response.status_code, 200)
            # Ensure that no tasks were created (all responses were recognized)
            self.assertEqual(0, Task.objects.count(), f"Response text: {response_text}")
            self.assertEqual(i + 1, NPSResponse.objects.count(), f"Response text: {response_text}")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class DailyOutgoingSMSSummaryTestCase(TestCase):
    def test_one_country_generate_distinct_results(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory(message_type="bulk")
        SMSRecipient.objects.create(
            recipient=customer,
            gateway_name="AfricasTalking",
            message=outgoing_sms
        )

        update_dailyoutgoingsmssummary()

        self.assertEqual(DailyOutgoingSMSSummary.objects.count(), 3)  # one for each of Kenya, Uganda, Zamiba

        # Only one of the summaries should countain a message (Kenya).
        self.assertEqual(DailyOutgoingSMSSummary.objects.filter(count=1).count(), 1)

    def test_multiple_country_generate_distinct_results(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory(message_type="bulk")
        SMSRecipient.objects.create(
            recipient=customer,
            gateway_name="AfricasTalking",
            message=outgoing_sms
        )

        customer2 = CustomerFactory(border0=Border.objects.get(country='Zambia', level=0), phones=None, add_main_phones=['+260950000000'])
        outgoing_sms2 = OutgoingSMSFactory(message_type="bulk")
        SMSRecipient.objects.create(
            recipient=customer2,
            gateway_name="AfricasTalking",
            message=outgoing_sms2
        )

        update_dailyoutgoingsmssummary()

        self.assertEqual(DailyOutgoingSMSSummary.objects.count(), 3)  # one for each of Kenya, Uganda, Zamiba

        # Two of the summaries should countain a message (Kenya and Zamiba).
        self.assertEqual(DailyOutgoingSMSSummary.objects.filter(count=1).count(), 2)
