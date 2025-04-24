from unittest.mock import patch

from django.test import TestCase

import phonenumbers

from calls.tests.util import generate_phone_number
from digifarm.constants import DIGIFARM_PHONE_NUMBER_PREFIX


class DigifarmUtilsTestCase(TestCase):
    def test_generate_phone_number_always_returns_valid_phone_number(self):
        # numbers without the prefix
        VALID_NUMBER = '5990173921610'
        numbers = ['7079168675982', '7079168675981', VALID_NUMBER]

        self.call_count = 0

        def rand_int_return(*args, **kwargs):
            num = numbers[self.call_count]
            self.call_count += 1
            return num

        with patch('calls.tests.util.randint', side_effect=rand_int_return) as mocked_randint:
            phone_number = generate_phone_number(prefix=phonenumbers.country_code_for_region('DE'), length=9)
            self.assertEqual('{}{}'.format(DIGIFARM_PHONE_NUMBER_PREFIX, VALID_NUMBER), phone_number)

        self.assertEqual(self.call_count, 3)
        self.assertEqual(mocked_randint.call_count, 3)
