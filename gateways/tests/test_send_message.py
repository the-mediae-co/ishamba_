from django.test import override_settings

from celery import shared_task

from core.test.cases import TestCase
from customers.tests.factories import CustomerFactory
from gateways import gateways
from gateways.africastalking.testing import activate_success_response
from sms.constants import OUTGOING_SMS_TYPE
from sms.models.outgoing import OutgoingSMS
from sms.tests.factories import OutgoingSMSFactory
from world.models import Border


@shared_task
def dummy_results_callback(results, extra=None):
    return 'dummy_results_callback'


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class SendMessageTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.gateway = gateways.get_gateway(gateways.AT)
        self.outgoing_sms = OutgoingSMSFactory(message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)


    @activate_success_response
    def test_uganda_recipient_sends_correctly(self):
        customer = CustomerFactory(border0=Border.objects.get(country='Uganda', level=0), phones=None, add_main_phones=['+256712344567'])
        self.gateway.send_message(self.outgoing_sms, [customer.pk], sender='iShambaU')

        self.assertEqual(1, OutgoingSMS.objects.count())

    @activate_success_response
    def test_zambia_recipient_sends_correctly(self):
        customer = CustomerFactory(border0=Border.objects.get(country='Zambia', level=0), phones=None, add_main_phones=['+260950000000'])
        gateway = gateways.get_gateway(gateways.ATZMB)
        gateway.send_message(self.outgoing_sms, [customer.pk], sender='iMunda')

        self.assertEqual(1, OutgoingSMS.objects.count())
