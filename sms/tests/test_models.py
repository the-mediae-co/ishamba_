from django.db import IntegrityError, connection

from core.test.cases import TestCase

from gateways.africastalking.testing import activate_success_response

from customers.tests.factories import CustomerFactory
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS, SMSRecipient
from .factories import OutgoingSMSFactory


class OutgoingSMSTestCase(TestCase):

    @activate_success_response
    def test_send_works(self):
        client = connection.tenant.schema_name
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory(message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)
        outgoing_sms.send(client, [customer], sender='21606')

        outgoing_sms.refresh_from_db()
        self.assertEqual(OUTGOING_SMS_TYPE.INDIVIDUAL, outgoing_sms.message_type)
        self.assertEqual(1, SMSRecipient.objects.filter(message_id=outgoing_sms.id).count())
        self.assertEqual(1, SMSRecipient.objects.filter(recipient_id=customer.id).count())
        smsr = SMSRecipient.objects.filter(message_id=outgoing_sms.id).first()
        self.assertEqual(1, smsr.page_index)
        self.assertTrue(smsr.gateway_msg_id)
        self.assertEqual(outgoing_sms, smsr.message)
        self.assertEqual(customer, smsr.recipient)


class SMSRecipientTestCase(TestCase):

    def test_duplicate_smsrecipient_not_allowed(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()

        SMSRecipient.objects.create(recipient=customer,
                                    message=outgoing_sms,
                                    page_index=1)

        with self.assertRaises(IntegrityError):
            SMSRecipient.objects.create(recipient=customer,
                                        message=outgoing_sms,
                                        page_index=1)

    def test_multi_page_smsrecipient_works(self):
        customer = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()

        SMSRecipient.objects.create(recipient=customer,
                                    message=outgoing_sms,
                                    page_index=1)

        try:
            SMSRecipient.objects.create(recipient=customer,
                                        message=outgoing_sms,
                                        page_index=2)
        except IntegrityError:
            self.fail("IntegrityError raised inappropriately")

    def test_separate_recipients_works(self):
        customer1 = CustomerFactory()
        customer2 = CustomerFactory()
        outgoing_sms = OutgoingSMSFactory()

        SMSRecipient.objects.create(recipient=customer1,
                                    message=outgoing_sms,
                                    page_index=1)

        try:
            SMSRecipient.objects.create(recipient=customer2,
                                        message=outgoing_sms,
                                        page_index=1)
        except IntegrityError:
            self.fail("IntegrityError raised inappropriately")

    def test_separate_messages_works(self):
        customer = CustomerFactory()
        outgoing_sms1 = OutgoingSMSFactory()
        outgoing_sms2 = OutgoingSMSFactory()

        SMSRecipient.objects.create(recipient=customer,
                                    message=outgoing_sms1,
                                    page_index=1)

        try:
            SMSRecipient.objects.create(recipient=customer,
                                        message=outgoing_sms2,
                                        page_index=1)
        except IntegrityError:
            self.fail("IntegrityError raised inappropriately")


class SMSBaseTestCase(TestCase):

    # def test_get_status_value(self):
    #     outgoing_sms = BaseOutgoingSMS()
    #
    #     self.assertEqual(outgoing_sms.get_status_value('Sent'),
    #                      BaseOutgoingSMS.SENT)

    def test_extant_recipients_unsaved(self):
        sms = OutgoingSMS()
        self.assertQuerysetEqual(sms.get_extant_recipients(),
                                 SMSRecipient.objects.none())
