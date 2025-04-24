from django.core.exceptions import ValidationError

from core.test.cases import TestCase

import phonenumbers

from customers.tests.factories import CustomerFactory
from sms.utils import prepare_numbers, validate_number


class PrepareNumbersTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.valid_number_obj = CustomerFactory().main_phone
        cls.valid_number_obj_2 = CustomerFactory().main_phone

        cls.list_of_valid_inputs = [cls.valid_number_obj,
                                    cls.valid_number_obj_2]

        cls.valid_number_obj_result = str(cls.valid_number_obj)
        cls.valid_number_obj_2_result = str(cls.valid_number_obj_2)

        cls.valid_int_string = '+254-203570095'  # Africa's Talking

        cls.non_kenyan_number_obj = phonenumbers.parse('01706360676', 'GB')  # UK number
        cls.non_kenyan_string = '+441706360676'
        cls.expected_result = ','.join((cls.valid_number_obj_result,
                                        cls.valid_number_obj_2_result))

    def test_cleans_a_valid_list_of_inputs(self):
        prepare_numbers(self.list_of_valid_inputs)
        try:
            prepare_numbers(self.list_of_valid_inputs)
        except Exception:
            self.fail("prepare_numbers() with a list of valid inputs raised "
                      "an error unexpectedly")

    def test_fails_for_plain_strings(self):
        fodder = [self.valid_int_string]
        self.assertRaises(AttributeError, prepare_numbers, fodder)

    def test_fails_for_non_kenyan_numbers(self):
        fodder = [self.non_kenyan_number_obj]
        result, failures = prepare_numbers(fodder)
        self.assertEqual(result, '')
        self.assertEqual(failures, self.non_kenyan_string)

    def test_returns_correct_format(self):
        result, failures = prepare_numbers(self.list_of_valid_inputs)
        self.assertEqual(result, self.expected_result)


class ValidateNumbersTests(TestCase):

    def setUp(self):
        super().setUp()
        self.customer = CustomerFactory(blank=True)
        self.phone = self.customer.phones.first()
        self.valid_number_obj = self.phone.number
        self.valid_number_obj_result = str(self.valid_number_obj)

        self.non_kenyan_number_obj = phonenumbers.parse('01706360676', 'GB')  # UK number

    def test_validate_number_raises_no_error_for_valid_number(self):
        validate_number(self.valid_number_obj)

    def test_validate_number_fails_for_non_kenyan_number_obj(self):
        self.assertRaises(ValidationError, validate_number, self.non_kenyan_number_obj)

    def test_returns_correct_format(self):
        result = validate_number(self.valid_number_obj)
        self.assertTrue(isinstance(result, bool))


class PhonenumberValidatorTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.valid_kenya_1 = '+25420882270'  # Mediae fax number
        self.valid_kenya_2 = '+254771117250'  # Mediae tel number
        self.valid_uganda = '+256701234567'

        self.invalid_country = '+4927115661189472'
        self.invalid_number = '123456789'

    def test_valid_single_kenya_recipient(self):
        self.assertTrue(validate_number(self.valid_kenya_1, allow_international=False))

    def test_valid_single_kenya_recipient_i18n_true(self):
        self.assertTrue(validate_number(self.valid_kenya_1, allow_international=True))

    def test_valid_single_uganda_recipient(self):
        self.assertTrue(validate_number(self.valid_uganda, allow_international=False))

    def test_valid_single_uganda_recipient_i18n_true(self):
        self.assertTrue(validate_number(self.valid_uganda, allow_international=True))

    def test_valid_single_invalid_country(self):
        self.assertRaises(ValidationError, validate_number,
                          self.invalid_country, allow_international=False)

    def test_valid_single_invalid_country_i18n_true(self):
        self.assertTrue(validate_number(self.invalid_country, allow_international=True))

    def test_valid_single_invalid_number(self):
        self.assertRaises(ValidationError, validate_number,
                          self.invalid_number, allow_international=False)
