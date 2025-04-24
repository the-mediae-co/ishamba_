import datetime
import re
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.timezone import localtime, make_aware, now

from dateutil.relativedelta import relativedelta
from gateways.africastalking.testing import activate_success_response
from django_tenants.test.client import TenantClient as Client

from core.test.cases import TestCase

from customers.models import Customer
from customers.tests.factories import CustomerFactory
from sms import constants as s_constants
from sms import utils
from sms.models.outgoing import SMSRecipient
from sms.tests.utils import get_sms_data
from tasks.models import Task

from .. import constants
from ..models import VerifyInStoreOffer, Voucher

valid_ip = s_constants.SMS_API_IPS[0]
to_phone = '12345'


class VerifyInStoreOfferVoucherCreationTests(TestCase):

    def setUp(self):
        super().setUp()
        self.offer = VerifyInStoreOffer.objects.create(
            name='Big discount',
            expiry_date=localtime(now()).date() + relativedelta(months=1),
            message="XXXXXX",
            confirmation_message="Code is valid. Give the customer a discount.",
        )

    def test_properties(self):
        self.assertEqual(self.offer.is_current(), True)

    def test_simple_creation(self):
        generated = self.offer.generate_codes(1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(len(generated), 1)
        voucher = Voucher.objects.all()[0]
        self.assertEqual(voucher, generated[0])
        self.assertEqual(voucher.offer.specific, self.offer)
        self.assertEqual(bool(voucher.code), True)
        self.assertEqual(bool(voucher.used_by), False)
        self.assertEqual(bool(voucher.offer.is_current), True)

    def test_multiple_generation(self):
        generated = self.offer.generate_codes(100)
        self.assertEqual(Voucher.objects.count(), 100)
        self.assertEqual(len(generated), 100)

    def test_consecutive_generation(self):
        first_generated = self.offer.generate_codes(50)
        self.assertEqual(Voucher.objects.count(), 50)
        self.assertEqual(len(first_generated), 50)
        # convert the list to a queryset
        first_generated = Voucher.objects.filter(id__in=[v.id for v in first_generated])
        self.assertEqual(first_generated.latest('number').number, 49)
        # second batch
        second_generated = self.offer.generate_codes(40)
        self.assertEqual(Voucher.objects.count(), 90)
        self.assertEqual(len(second_generated), 40)
        # convert the list to a queryset
        second_generated = Voucher.objects.filter(id__in=[v.id for v in second_generated])
        self.assertEqual(second_generated.earliest('number').number, 50)
        self.assertEqual(second_generated.latest('number').number, 89)


class MessageRegExTests(TestCase):

    GOOD_MESSAGES = {
        6: ["this is:XXXXXX not separated but could be okay",
            "separating with -XXXXXX a hyphen is maybe okay",
            "at the end of the string XXXXXX",
            "in the middle XXXXXX of the string",
            "XXXXXX GOOD at the start of the string"],
        5: ["this is XXXXX too short"],
        7: ["this is XXXXXXX too long"],
    }

    GENERALLY_BAD_MESSAGES = [
        "this isXXXXXX not separated",
        "this is:XXXXXXnot separated",
        "separating with _XXXXXX underscores is bad",
        "at the XXXXXX middle and end of the string XXXXXX",
        "in the middle XXXXXX twice XXXXXX too",
        "XXXXXX at the start and repeated XXXXXX in the middle of the string is bad",
    ]

    BAD_MESSAGES = {
        5: GOOD_MESSAGES[6] + GOOD_MESSAGES[7] + GENERALLY_BAD_MESSAGES,
        6: GOOD_MESSAGES[5] + GOOD_MESSAGES[7] + GENERALLY_BAD_MESSAGES,
        7: GOOD_MESSAGES[5] + GOOD_MESSAGES[6] + GENERALLY_BAD_MESSAGES,
    }

    def create_offer(self, message):
        return VerifyInStoreOffer.objects.create(
            name='Free stuff',
            expiry_date=localtime(now()).date() + relativedelta(months=1),
            message=message,
            confirmation_message="This voucher is verified. Give the customer a discount.",
        )

    def test_regex_stringformats_correctly(self):
        pattern = constants.CODE_REGEX_TEMPLATE.format(code_length=6)
        self.assertEqual(pattern, r"^(?!.*X{6}.*X{6}).*\bX{6}\b.*$")

    def test_regex_standalone_five(self):
        pattern = constants.CODE_REGEX_TEMPLATE.format(code_length=5)
        for message in self.BAD_MESSAGES[5]:
            result = re.match(pattern, message)
            self.assertEqual(result, None)
        for message in self.GOOD_MESSAGES[5]:
            result = re.match(pattern, message)
            self.assertTrue(result)

    def test_regex_standalone_six(self):
        pattern = constants.CODE_REGEX_TEMPLATE.format(code_length=6)
        for message in self.BAD_MESSAGES[6]:
            result = re.match(pattern, message)
            self.assertEqual(result, None)
        for message in self.GOOD_MESSAGES[6]:
            result = re.match(pattern, message)
            self.assertTrue(result)

    def test_regex_standalone_seven(self):
        pattern = constants.CODE_REGEX_TEMPLATE.format(code_length=7)
        for message in self.BAD_MESSAGES[7]:
            result = re.match(pattern, message)
            self.assertEqual(result, None)
        for message in self.GOOD_MESSAGES[7]:
            result = re.match(pattern, message)
            self.assertTrue(result)

    def test_offer_message_code_placeholder_too_long(self):
        with self.assertRaises(ValidationError):
            offer = self.create_offer(message="Here's your discount code: XXXXXXX!")
            offer.clean_fields()

    def test_offer_message_code_placeholder_too_short(self):
        with self.assertRaises(ValidationError):
            offer = self.create_offer(message="Here's your discount code: XXXXX!")
            offer.clean_fields()

    def test_offer_message_code_placeholder_okay(self):
        try:
            offer = self.create_offer(message="Here's your discount code: XXXXXX!")
            offer.clean_fields()
        except Exception:
            self.fail("Creating offer with an expected-good message raised an error unexpectedly!")


class VerifyInStoreVoucherProcessingTests(TestCase):

    now = make_aware(datetime.datetime(2012, 5, 1, 13, 0, 0), datetime.timezone.utc)
    offer_has_expired_time = make_aware(datetime.datetime(2012, 6, 2, 9, 0, 0), datetime.timezone.utc)

    def setUp(self):
        super().setUp()
        self.shop_keeper_phone = "+254720000091"

        self.offer = VerifyInStoreOffer.objects.create(
            name='Big savings',
            message="XXXXXX",
            confirmation_message="Code is valid. Give the customer a discount.",
            expiry_date=datetime.date(2012, 6, 1),
        )

        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)

    @patch('payments.models.now', return_value=now)
    @activate_success_response
    def test_simple_voucher_use_from_unknown_verifier(self, mock_payments_now):
        voucher = self.offer.generate_codes(1)[0]
        data = get_sms_data(voucher.code, self.shop_keeper_phone, to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)
        # incidental, but check that the 'customer' was created
        try:
            new_customer = Customer.objects.get(phones__number=self.shop_keeper_phone)
        except Customer.DoesNotExist:
            self.fail('New customer not created when receiving voucher from unknown number')

        # only sent one message
        receipts = SMSRecipient.objects.filter(recipient=new_customer)
        self.assertEqual(receipts.count(), 1)

        # the customer received one confirmation SMS response
        sent_sms = receipts.first().message
        self.assertEqual(sent_sms.text, voucher.offer.confirmation_message)

        # no task was created
        self.assertEqual(Task.objects.count(), 0)
        # the voucher is used by the customer
        voucher = Voucher.objects.get(id=voucher.id)
        self.assertEqual(voucher.used_by, new_customer)
        self.assertEqual(voucher.is_valid(), False)

    @patch('customers.models.timezone.now', return_value=now)
    @patch('payments.models.now', return_value=now)
    @activate_success_response
    def test_repeat_voucher_use_from_unknown_verifier(self, mock_payments_now, mock_customers_now):
        voucher = self.offer.generate_codes(1)[0]

        # If duplicates are sent too close to each other, the second is squelched from action.
        first_time = self.now
        second_time = first_time + datetime.timedelta(days=1, hours=1)

        data1 = get_sms_data(voucher.code, self.shop_keeper_phone, to_phone, date=first_time)
        response = self.client.post(reverse('sms_api_callback'), data1)
        self.assertEqual(response.status_code, 200)

        data2 = get_sms_data(voucher.code, self.shop_keeper_phone, to_phone, date=second_time)
        response = self.client.post(reverse('sms_api_callback'), data2)
        self.assertEqual(response.status_code, 200)

        # the customer was created
        new_customer = Customer.objects.get(phones__number=self.shop_keeper_phone)

        used_msg, sender = utils.get_populated_sms_templates_text(settings.SMS_VOUCHER_ALREADY_USED,
                                                                  new_customer,
                                                                  voucher=voucher)

        # sent two messages
        receipts = SMSRecipient.objects.filter(recipient=new_customer)
        self.assertEqual(receipts.count(), 2)

        messages = [r.message.text for r in receipts]

        # the customer received one confirmation and one 'reject' SMS response
        self.assertIn(voucher.offer.confirmation_message, messages)
        self.assertIn(used_msg, messages)
        self.assertEqual('21606', sender)

        # no task was created
        self.assertEqual(Task.objects.all().count(), 0)

        # the voucher is used by the customer
        voucher = Voucher.objects.get(id=voucher.id)
        self.assertEqual(voucher.used_by, new_customer)
        self.assertEqual(voucher.is_valid(), False)

    @patch('payments.models.now', return_value=offer_has_expired_time)
    @activate_success_response
    def test_using_voucher_after_expiry_date_generates_invalid_response(self, mock_payments_now):
        voucher = self.offer.generate_codes(1)[0]
        data = get_sms_data(voucher.code, self.shop_keeper_phone, to_phone)
        response = self.client.post(reverse('sms_api_callback'), data)
        self.assertEqual(response.status_code, 200)

        # the customer was created
        new_customer = Customer.objects.get(phones__number=self.shop_keeper_phone)
        message, sender = utils.get_populated_sms_templates_text(settings.SMS_VOUCHER_OFFER_EXPIRED,
                                                                 new_customer,
                                                                 voucher=voucher)

        # only sent one message
        receipts = SMSRecipient.objects.filter(recipient=new_customer)
        self.assertEqual(receipts.count(), 1)

        # the customer received one 'reject' response'
        sent_sms = receipts.first().message
        self.assertEqual(sent_sms.text, message)
        self.assertEqual('21606', sender)

        # the voucher is not marked used
        voucher = Voucher.objects.get(id=voucher.id)
        self.assertEqual(voucher.used_by, None)

    @patch('payments.models.now', return_value=now)
    @activate_success_response
    def test_offer_takeup(self, mock_payments_now):
        vouchers = self.offer.generate_codes(10)
        data = get_sms_data(vouchers[0].code, self.shop_keeper_phone, to_phone)
        self.client.post(reverse('sms_api_callback'), data)
        # takeup is 10%
        self.assertEqual(self.offer.take_up, "10.0&nbsp;%")
        # do it again
        self.client.post(reverse('sms_api_callback'), data)
        # takeup is unchanged
        self.assertEqual(self.offer.take_up, "10.0&nbsp;%")
        # submit a new voucher
        data = get_sms_data(vouchers[1].code, self.shop_keeper_phone, to_phone)
        self.client.post(reverse('sms_api_callback'), data)
        # takeup is 20%
        self.assertEqual(self.offer.take_up, "20.0&nbsp;%")


class OfferVerifyViewTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.customer = CustomerFactory()
        self.client = Client(self.tenant, REMOTE_ADDR=valid_ip)

        User = get_user_model()
        self.operator = User.objects.create_user('foo', password='foo')
        self.client.login(username='foo', password='foo')

        self.offer = VerifyInStoreOffer.objects.create(
            name='Test offer',
            message='X' * constants.CODE_LENGTH,
            expiry_date=localtime(now()).date() + relativedelta(days=1)
        )
        self.expired_offer = VerifyInStoreOffer.objects.create(
            name='Test offer (expired)',
            message='X' * constants.CODE_LENGTH,
            expiry_date=localtime(now()).date() - relativedelta(days=1)
        )

        self.valid_code = self.offer.generate_codes(1)[0]

        self.used_code = self.offer.generate_codes(1)[0]
        self.used_code.used_by = self.customer
        self.used_code.save()

        self.expired_code = self.expired_offer.generate_codes(1)[0]

    def test_authorised_user_can_view_page(self):
        resp = self.client.get(reverse('offer_verify'))
        self.assertEqual(resp.status_code, 200)

    def test_unauthorised_user_cant_view_page(self):
        self.client.logout()  # client is logged in by setUp so log it out
        resp = self.client.get(reverse('offer_verify'))
        self.client.get
        self.assertRedirects(
            resp,
            '{}?next={}'.format(reverse('login'), reverse('offer_verify')))

    def test_valid_submission(self):
        resp = self.client.post(
            reverse('offer_verify'),
            data={'phone': self.customer.main_phone, 'code': self.valid_code},
            follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['messages']), 1)
        self.valid_code.refresh_from_db()
        self.assertFalse(self.valid_code.is_valid())

    def test_invalid_phonenumber(self):
        resp = self.client.post(
            reverse('offer_verify'),
            data={'phone': '+25420882271', 'code': self.valid_code})
        self.assertFormError(
            resp.context['form'],
            'phone',
            '+25420882271 does not correspond to an existing customer.')

    def test_invalid_code(self):
        resp = self.client.post(
            reverse('offer_verify'),
            data={'phone': self.customer.main_phone, 'code': 'AAAAAA'})
        self.assertFormError(
            resp.context['form'],
            'code',
            'The voucher AAAAAA does not exist.')

    def test_used_code(self):
        resp = self.client.post(
            reverse('offer_verify'),
            data={'phone': self.customer.main_phone, 'code': self.used_code})
        self.assertFormError(
            resp.context['form'],
            'code',
            'The voucher {} has already been used.'.format(self.used_code))

    def test_expired_code(self):
        resp = self.client.post(
            reverse('offer_verify'),
            data={'phone': self.customer.main_phone, 'code': self.expired_code})
        self.assertFormError(
            resp.context['form'],
            'code',
            'The voucher {} has expired.'.format(self.expired_code))
