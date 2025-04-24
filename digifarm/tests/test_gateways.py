from unittest.mock import patch, call
from faker import Faker
from unittest import skip

from core.test.cases import TestCase

from customers.models import Customer
from sms.constants import OUTGOING_SMS_TYPE
# from ..gateways import DigifarmSMSGateway
from sms.models import OutgoingSMS, SMSRecipient

from sms.tests.factories import OutgoingSMSFactory
from digifarm.testing import activate_success_response


class DigifarmSMSGatewayTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.outgoing_sms = OutgoingSMSFactory(message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)

    @skip("Digifarm sending is temporarily disabled")
    @patch('digifarm.gateways.send_digifarm_sms')
    def test_send_message_creates_batched_task(self, send_sms_mock):
        DigifarmSMSGateway.RECIPIENT_BATCH_SIZE = 2
        customer1 = Customer.objects.create(phone='+4921231231231233', digifarm_farmer_id='Farmer1')
        customer2 = Customer.objects.create(phone='+4921231231231234', digifarm_farmer_id='Farmer2')
        customer3 = Customer.objects.create(phone='+4921231231231235', digifarm_farmer_id='Farmer3')

        gateway = DigifarmSMSGateway()
        gateway.send_message([customer1.phone, customer2.phone, customer3.phone], self.outgoing_sms)

        self.assertEqual(2, len(send_sms_mock.call_args_list))
        first_call = send_sms_mock.call_args_list[0]
        params = first_call[0]
        self.assertEqual(2, len(params[0]))  # Sent to two farmers
        self.assertIn(customer1.digifarm_farmer_id, params[0])
        self.assertIn(customer2.digifarm_farmer_id, params[0])
        self.assertEqual(self.outgoing_sms, params[1])

        second_call = send_sms_mock.call_args_list[1]
        params = second_call[0]
        self.assertEqual(1, len(params[0]))  # Sent to one farmer
        self.assertIn(customer3.digifarm_farmer_id, params[0])
        self.assertEqual(self.outgoing_sms, params[1])

    @skip("Digifarm sending is temporarily disabled")
    @patch('digifarm.gateways.send_digifarm_sms_by_phone_numbers')
    def test_send_message_with_task_kwargs(self, send_sms_mock):
        customer = Customer.objects.create(phone='+4921231231231233', digifarm_farmer_id='Farmer1')

        gateway = DigifarmSMSGateway()
        gateway.send_message([customer.phone],
                             self.outgoing_sms,
                             task_kwargs={'eta': 'test'})

        send_sms_mock.apply_async.assert_called_once_with(
            ([customer.phone], self.outgoing_sms),
            eta='test'
        )

    @skip("Digifarm sending is temporarily disabled")
    @activate_success_response
    def test_send_message_creates_recipients(self):
        DigifarmSMSGateway.RECIPIENT_BATCH_SIZE = 2
        customer1 = Customer.objects.create(phone='+4921231231231233', digifarm_farmer_id='Farmer1')
        customer2 = Customer.objects.create(phone='+4921231231231234', digifarm_farmer_id='Farmer2')
        customer3 = Customer.objects.create(phone='+4921231231231235', digifarm_farmer_id='Farmer3')

        gateway = DigifarmSMSGateway()
        gateway.send_message([customer1.phone, customer2.phone, customer3.phone], self.outgoing_sms)

        self.assertEqual(3, SMSRecipient.objects.count())
        self.assertEqual(1, OutgoingSMS.objects.count())
        for smsr in SMSRecipient.objects.all():
            self.assertEqual(self.outgoing_sms.id, smsr.message.id)
            self.assertEqual(200, int(smsr.failure_reason))
            self.assertEqual('Success', smsr.delivery_status)

        for c in Customer.objects.all():
            self.assertTrue(SMSRecipient.objects.filter(recipient_id=c.id).exists())

    @skip("Digifarm sending is temporarily disabled")
    @activate_success_response
    def test_long_message_does_not_paginate_creates_single_recipients(self):
        customer1 = Customer.objects.create(phone='+4921231231231233', digifarm_farmer_id='Farmer1')
        long_msg = OutgoingSMSFactory(message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)
        faker = Faker()
        long_msg.text = faker.paragraph(nb_sentences=5)
        long_msg.save()

        gateway = DigifarmSMSGateway()
        gateway.send_message([customer1.phone], long_msg)

        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(2, OutgoingSMS.objects.count())
        smsr = SMSRecipient.objects.first()
        self.assertEqual(long_msg.id, smsr.message.id)
        self.assertEqual(200, int(smsr.failure_reason))
        self.assertEqual('Success', smsr.delivery_status)
        self.assertEqual(customer1.id, smsr.recipient_id)
