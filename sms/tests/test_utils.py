from core.test.cases import TestCase

from customers.tests.factories import CustomerFactory
from sms import constants, utils


class SMSValidatorTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.valid_1 = 'Foo bar baz text'

        self.valid_long = 'a' * (constants.MAX_SMS_LEN + 1)

        self.invalid = 'Foo bar א'

    def test_valid_message_validates_without_len_check(self):
        self.assertTrue(utils.validate_sms(self.valid_1))

    def test_valid_message_validates_with_len_check(self):
        self.assertTrue(utils.validate_sms(self.valid_1, check_len=True))

    def test_valid_long_message_validates_without_len_check(self):
        self.assertTrue(utils.validate_sms(self.valid_long))

    def test_valid_long_message_does_not_validate_with_len_check(self):
        self.assertFalse(utils.validate_sms(self.valid_long, check_len=True))

    def test_invalid_does_not_validate(self):
        self.assertFalse(utils.validate_sms(self.invalid))


class TestTemplateMacroExpansions(TestCase):
    def test_call_centre_expansion_with_customer(self):
        customer = CustomerFactory()
        text = 'Please MPesa {month_price} for one month'
        result = utils.populate_templated_text(text, customer)

        self.assertEqual('Please MPesa 10.00 kshs for one month', result)

    def test_call_centre_expansion_without_customer(self):
        text = 'Please MPesa {month_price} for one month'
        result = utils.populate_templated_text(text, None)
        self.assertEqual('Please MPesa 10.00 kshs for one month', result)

    def test_shortcode_expansion_with_customer(self):
        customer = CustomerFactory()
        text = 'Please sms {shortcode} for help'
        result = utils.populate_templated_text(text, customer)
        self.assertEqual('Please sms 21606 for help', result)

    def test_till_number_expansion_with_customer(self):
        customer = CustomerFactory()
        text = 'Please MPesa to {till_number} for your subscription'
        result = utils.populate_templated_text(text, customer)
        self.assertEqual('Please MPesa to 21606 for your subscription', result)

    def test_year_price_expansion_with_customer(self):
        customer = CustomerFactory()
        text = 'Please MPesa {year_price} for one month'
        result = utils.populate_templated_text(text, customer)
        self.assertEqual('Please MPesa 110.00 kshs for one month', result)
