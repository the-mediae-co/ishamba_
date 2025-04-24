from unittest import skip
from unittest.mock import patch

from django.db import ProgrammingError
from django.db import connection
from django.test import override_settings

from core.test.cases import TestCase

from gateways.africastalking.testing import activate_success_response, activate_unsupported_number_type_response

from customers.models import Customer, CustomerPhone
from customers.tests.factories import CustomerFactory, CustomerPhoneFactory
from customers.tests.utils import CreateCustomersMixin
from sms.models import SMSRecipient, OutgoingSMS
from sms.constants import KENYA_COUNTRY_CODE, OUTGOING_SMS_TYPE
from world.models import Border


@override_settings(SEND_SMS=True)
class SendTests(TestCase, CreateCustomersMixin):

    def setUp(self):
        from .factories import OutgoingSMSFactory
        super().setUp()
        self.create_customers()
        self.outgoing_sms = OutgoingSMSFactory()

    @activate_success_response
    @skip('We temporarily allow bare number lists')
    def test_send_raises_error_with_list_of_phone_number_strings(self):
        list_of_phone_number_strings = [
            c.format_phone_number('E164') for
            c in Customer.objects.filter(has_requested_stop=False)]

        with self.assertRaises(ProgrammingError):
            self.outgoing_sms.send(TestCase.get_test_schema_name(), list_of_phone_number_strings, sender='iShamba')

    @activate_success_response
    def test_send_raises_error_with_single_phone_number_string(self):
        list_of_phone_number_strings = [
            c.format_phone_number('E164') for
            c in Customer.objects.filter(has_requested_stop=False)]

        with self.assertRaises(ProgrammingError):
            self.outgoing_sms.send(TestCase.get_test_schema_name(), list_of_phone_number_strings[0], sender='iShamba')

    @activate_success_response
    def test_send_works_when_given_customers_queryset(self):
        customers_queryset = Customer.objects.should_receive_messages()
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customers_queryset, sender='iShamba')
        # Only Kenya recipients have SMSRecipient objects created
        count = customers_queryset.filter(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").filter(
                                          has_requested_stop=False).count()
        self.assertEqual(count, SMSRecipient.objects.count(),
                         msg="Number of AT messages sent is incorrect")

    @activate_success_response
    def test_send_works_with_values_list_queryset(self):
        customers = list(Customer.objects.all())
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba')
        # Only Kenya recipients have SMSRecipient objects created
        count = Customer.objects.filter(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").filter(
                                          has_requested_stop=False).count()
        self.assertEqual(count, SMSRecipient.objects.count(),
                         msg="Number of AT messages sent is incorrect")

    @activate_success_response
    def test_basic_send_sms_one_recipient(self):
        customer = Customer.objects.should_receive_messages().first()
        sms = OutgoingSMS.objects.create(text='test',
                                         message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)
        sms.send(connection.tenant.schema_name, [customer], sender='iShamba')
        self.assertEqual(2, OutgoingSMS.objects.count(),  # One created in setup, one created here
                         msg="Number of messages sent is incorrect")
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(customer.phones.first().number, SMSRecipient.objects.first().extra['number'])

    @activate_success_response
    def test_basic_send_outgoing_one_recipient(self):
        customer = Customer.objects.should_receive_messages().first()
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')
        self.assertEqual(1, SMSRecipient.objects.count(),
                         msg="Number of messages sent is incorrect")
        self.assertEqual(customer.phones.first().number, SMSRecipient.objects.first().extra['number'])

    @activate_unsupported_number_type_response
    def test_send_sms_one_recipient_non_mobile_non_DF_number(self):
        customer = Customer.objects.should_receive_messages().first()
        sms = OutgoingSMS.objects.create(text='test',
                                         message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)
        sms.send(connection.tenant.schema_name, [customer], sender='iShamba')
        customer.refresh_from_db()
        self.assertEqual(True, customer.has_requested_stop,
                         msg="Customer's has_requested_stop was not set")

    @activate_unsupported_number_type_response
    def test_send_sms_one_recipient_non_mobile_africas_talking_number(self):
        customer = Customer.objects.should_receive_messages().first()
        customer.digifarm_farmer_id = 'df_abc123'
        customer.africas_talking_phone = customer.main_phone
        customer.save()
        self.assertFalse(customer.has_requested_stop)
        sms = OutgoingSMS.objects.create(text='test',
                                         message_type=OUTGOING_SMS_TYPE.INDIVIDUAL)
        sms.send(connection.tenant.schema_name, [customer], sender='iShamba')
        customer.refresh_from_db()
        self.assertTrue(customer.has_requested_stop, msg="Customer's has_requested_stop improperly set")

    @activate_unsupported_number_type_response
    def test_send_one_outgoing_recipient_non_mobile_non_df_number(self):
        customer = Customer.objects.should_receive_messages().first()
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')
        customer.refresh_from_db()
        self.assertEqual(0, SMSRecipient.objects.count(),
                         msg="Number of messages sent is incorrect")
        self.assertEqual(True, customer.has_requested_stop,
                         msg="Customer's has_requested_stop was not set")

    @activate_unsupported_number_type_response
    def test_send_one_outgoing_recipient_non_mobile_africas_talking_number(self):
        customer = Customer.objects.should_receive_messages().first()
        customer.digifarm_farmer_id = 'df_abc123'
        customer.africas_talking_phone = customer.main_phone
        customer.save()
        self.assertFalse(customer.has_requested_stop)
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')
        customer.refresh_from_db()
        self.assertEqual(0, SMSRecipient.objects.count(),
                         msg="Number of messages sent is incorrect")
        self.assertTrue(customer.has_requested_stop, msg="Customer's has_requested_stop improperly set")

    @activate_success_response
    def test_ignores_international_AT_recipients(self):
        customers = Customer.objects.filter(digifarm_farmer_id__isnull=True,
                                            phones__number__startswith="+492")
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba')
        # No messages created SMSRecipient (AT gateway)
        self.assertEqual(0, SMSRecipient.objects.count(),
                         msg="Number of AT messages sent is incorrect")

    @activate_success_response
    def test_send_correctly_ignores_opted_out_customers(self):
        customers = Customer.objects.all()
        # There's a bug in CustomerFactory that causes extras to be created...
        customers_count = Customer.objects.count()
        # Two customers have two phones
        self.assertEqual(customers_count + 2, CustomerPhone.objects.count())
        # ensure all customers were created
        # self.assertEqual(len(customers), len(self.customers))
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba')
        # The number of SMSRecipient records (AT gateway) now created is all
        # recipients with kenya phone numbers who have not requested stop
        count = customers.filter(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").filter(
                                 has_requested_stop=False).count()
        self.assertEqual(count,
                         SMSRecipient.objects.count(),
                         msg="Number of AT messages send is incorrect")

    @activate_success_response
    def test_we_cannot_even_send_to_an_individual_opted_out_customer_without_overriding(self):
        customer = Customer.objects.filter(has_requested_stop=True).first()

        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')

        self.assertEqual(0, SMSRecipient.objects.count(),
                         msg="Sent a message when we should not have")

    @activate_success_response
    def test_we_can_override_and_send_to_one_opted_out_customer(self):
        customer = Customer.objects.filter(has_requested_stop=True).first()

        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba', exclude_stopped_customers=False)
        # and the number of SMSRecipient records now created is one
        self.assertEqual(SMSRecipient.objects.count(), 1)

    @activate_success_response
    def test_we_can_override_and_send_to_one_opted_out_customer_by_customer(self):
        customers = Customer.objects.filter(has_requested_stop=True)
        customer = customers.first()

        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba', exclude_stopped_customers=False)
        # and the number of SMSRecipient records now created is one
        self.assertEqual(SMSRecipient.objects.count(), 1)

    @activate_success_response
    def test_duplicate_sending_reports_errors(self):
        # send to customer who .should_receive_messages == True
        customer = Customer.objects.filter(has_requested_stop=False,
                                           is_registered=True).first()

        with patch('sms.models.outgoing.logger') as logger_mock:
            self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')
            self.assertFalse(logger_mock.debug.called, False)

        # now try to send to all customers
        customers = Customer.objects.all()

        with patch('sms.models.outgoing.logger') as logger_mock:
            self.outgoing_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba')
            logger_mock.debug.assert_called_with(
                'Attempted to send %s id:%d to %d duplicate recipient%s',
                type(self.outgoing_sms), self.outgoing_sms.pk, 1, '')

    @activate_success_response
    def test_duplicate_sending_does_not_occur(self):
        customer = Customer.objects.filter(has_requested_stop=False,
                                           digifarm_farmer_id__isnull=True).first()

        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')
        # one SMSRecipient records created so far
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient.id)

        # now try to send to all customers, one of which is a duplicate
        customers = Customer.objects.all()
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba')

        count = customers.filter(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").filter(
                                 has_requested_stop=False).count()
        self.assertEqual(count, SMSRecipient.objects.count(),
                         msg="Wrong number of SMSRecipient objects created")

    @activate_success_response
    def test_sending_sets_recipient_fields_correctly(self):
        customer = Customer.objects.filter(has_requested_stop=False,
                                           digifarm_farmer_id__isnull=True).first()

        self.outgoing_sms.send(TestCase.get_test_schema_name(), customer, sender='iShamba')
        # one SMSRecipient record created so far
        self.assertEqual(1, SMSRecipient.objects.count())
        self.assertEqual(customer.id, SMSRecipient.objects.first().recipient.id)
        self.assertEqual(self.outgoing_sms.id, SMSRecipient.objects.first().message_id)

        # now try to send to all customers, one of which is a duplicate
        customers = Customer.objects.all()
        self.outgoing_sms.send(TestCase.get_test_schema_name(), customers, sender='21606')

        # but the number of SMSRecipient records now created is just 2 more (some are stopped)
        count = customers.filter(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}").filter(
                                 has_requested_stop=False).count()
        self.assertEqual(count, SMSRecipient.objects.count(),
                         msg="Wrong number of SMSRecipient objects created")
        self.assertEqual(count, SMSRecipient.objects.filter(message_id=self.outgoing_sms.id).count(),
                         msg="message_id of SMSRecipient objects not created")
        expected_extra = {'senders': {
            'Kenya': ['iShamba', '21606'],
        }}
        self.outgoing_sms.refresh_from_db()
        self.assertGreaterEqual(self.outgoing_sms.extra.items(), expected_extra.items())
        smsr = SMSRecipient.objects.filter(message=self.outgoing_sms).order_by('?').first()
        self.assertTrue('number' in smsr.extra)

        # now also send to a uganda recipient
        uganda = Border.objects.get(name='Uganda', level=0)
        uganda_customer = CustomerFactory(border0=uganda, name="uganda-customer", has_no_phones=True)
        uganda_phone = CustomerPhoneFactory(number="+256701234567", is_main=True, customer=uganda_customer)
        self.outgoing_sms.send(TestCase.get_test_schema_name(), [uganda_customer], sender='iShambaU')
        self.assertEqual(count + 1, SMSRecipient.objects.count(),
                         msg="Wrong number of SMSRecipient objects created")
        self.assertEqual(count + 1, SMSRecipient.objects.filter(message_id=self.outgoing_sms.id).count(),
                         msg="message_id of SMSRecipient objects not created")
        expected_extra = {'senders': {
            'Kenya': ['iShamba', '21606'],
            'Uganda': ['iShambaU'],
        }}
        self.outgoing_sms.refresh_from_db()
        self.assertGreaterEqual(self.outgoing_sms.extra.items(), expected_extra.items())


class BulkSendTests(TestCase):

    # @activate_success_response
    def setUp(self):
        from sms.tests.factories import OutgoingSMSFactory
        super().setUp()
        self.bulk_sms = OutgoingSMSFactory()

    @activate_success_response
    def test_sending_in_a_single_batch(self):
        beginning_smsr_count = SMSRecipient.objects.count()
        CustomerFactory.create_batch(120, blank=True)
        customers = Customer.objects.all()
        # There's a bug in CustomerFactory that causes extras to be created...
        customers_count = Customer.objects.count()
        # self.assertEqual(120, customers_count)
        self.assertEqual(customers_count, CustomerPhone.objects.count())
        self.bulk_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba')

        # 120 SMSRecipient records have been created
        self.assertEqual(beginning_smsr_count + customers_count, SMSRecipient.objects.count())

    @activate_success_response
    @skip('Long exec time and functionality already tested in mediae_crm')
    def test_sending_in_two_batches(self):
        # (self, to_, message_, from_=None, bulkSMSMode_=1, enqueue_=0, keyword_=None, linkId_=None):

        CustomerFactory.create_batch(6000, blank=True)
        phone_numbers_list = [c.main_phone for c in Customer.objects.all()]
        self.bulk_sms.send(TestCase.get_test_schema_name(), phone_numbers_list, sender='iShamba')

        # 6000 SMSRecipient records have been created
        self.assertEqual(SMSRecipient.objects.count(), 6000)

    @activate_success_response
    @skip('Long exec time and functionality already tested in mediae_crm')
    def test_sending_in_three_batches(self):
        # (self, to_, message_, from_=None, bulkSMSMode_=1, enqueue_=0, keyword_=None, linkId_=None):

        CustomerFactory.create_batch(12000, blank=True)
        phone_numbers_list = [c.main_phone for c in Customer.objects.all()]
        self.bulk_sms.send(TestCase.get_test_schema_name(), phone_numbers_list, sender='iShamba')

        # 12000 SMSRecipient records have been created
        self.assertEqual(SMSRecipient.objects.count(), 12000)

    @activate_success_response
    @skip("using_numbers functionality was moved in https://github.com/the-mediae-co/ishamba/pull/843 and subsequently removed in https://github.com/the-mediae-co/ishamba/pull/843")
    def test_sending_to_secondary_numbers_in_a_single_batch(self):
        beginning_smsr_count = SMSRecipient.objects.count()
        CustomerFactory.create_batch(120, blank=True)
        customers = Customer.objects.all()
        # There's a bug in CustomerFactory that causes extras to be created...
        customers_count = Customer.objects.count()
        self.assertEqual(customers_count, CustomerPhone.objects.count())
        using_numbers = []
        for c in customers:
            main_phone = c.main_phone
            main_number = int(str(c.main_phone)[1:])  # Remove the leading plus sign
            other_number = main_number + 10000
            other_phone = f'+{other_number}'
            CustomerPhone.objects.create(number=other_phone, is_main=False, customer=c)
            using_numbers.append(other_phone)

        kwargs = {'using_numbers': using_numbers}
        self.bulk_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba', **kwargs)

        # 120 SMSRecipient records have been created
        self.assertEqual(beginning_smsr_count + customers_count, SMSRecipient.objects.count())
        # Verify that the 'using_numbers' phone numbers were used instead of the main_number
        smsr_numbers = set(SMSRecipient.objects.filter(message=self.bulk_sms).values_list('extra__number', flat=True))
        customer_ids = customers.values_list('id', flat=True)
        customer_numbers = set(CustomerPhone.objects.filter(is_main=True,
                                                            customer__in=customer_ids).values_list('number', flat=True))
        matches = smsr_numbers.intersection(customer_numbers)
        self.assertEqual(0, len(matches))
        others = smsr_numbers.intersection(set(using_numbers))
        self.assertEqual(len(using_numbers), len(others))

    @activate_success_response
    @skip("using_numbers functionality was moved in https://github.com/the-mediae-co/ishamba/pull/843 and subsequently removed in https://github.com/the-mediae-co/ishamba/pull/843")
    def test_sending_too_many_secondary_numbers_ignores_extras(self):
        beginning_smsr_count = SMSRecipient.objects.count()
        CustomerFactory.create_batch(120, blank=True)
        customers = Customer.objects.all()
        # There's a bug in CustomerFactory that causes extras to be created...
        customers_count = Customer.objects.count()
        self.assertEqual(customers_count, CustomerPhone.objects.count())
        using_numbers = []
        for c in customers:
            main_phone = c.main_phone
            main_number = int(str(c.main_phone)[1:])  # Remove the leading plus sign
            other_number = main_number + 10000
            other_phone = f'+{other_number}'
            CustomerPhone.objects.create(number=other_phone, is_main=False, customer=c)
            using_numbers.append(other_phone)

        # Add an extra number, no associated with any of the customers
        extra_number = '+254720123456'
        using_numbers.append(extra_number)

        kwargs = {'using_numbers': using_numbers}
        self.bulk_sms.send(TestCase.get_test_schema_name(), customers, sender='iShamba', **kwargs)

        # 120 SMSRecipient records have been created
        self.assertEqual(beginning_smsr_count + customers_count, SMSRecipient.objects.count())
        # Verify that the 'using_numbers' phone numbers were used instead of the main_number
        smsr_numbers = set(SMSRecipient.objects.filter(message=self.bulk_sms).values_list('extra__number', flat=True))
        customer_ids = customers.values_list('id', flat=True)
        customer_numbers = set(CustomerPhone.objects.filter(is_main=True,
                                                            customer__in=customer_ids).values_list('number', flat=True))
        matches = smsr_numbers.intersection(customer_numbers)
        self.assertEqual(0, len(matches))
        others = smsr_numbers.intersection(set(using_numbers))
        self.assertEqual(len(using_numbers) - 1, len(others))
        self.assertNotIn(extra_number, smsr_numbers)
        self.assertIn(extra_number, using_numbers)
