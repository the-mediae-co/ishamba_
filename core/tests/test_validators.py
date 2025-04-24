from django.core.exceptions import ValidationError
from django.test import TestCase

from core.validators import GSMCharacterSetValidator


class TextMessageValidatorTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.validator = GSMCharacterSetValidator()

    def test_valid_string(self):
        self.validator('foo')

    def test_gsm_extended_characters(self):
        self.validator('[{~€}]')

    def test_empty_string(self):
        self.validator('')

    def test_invalid_character(self):
        with self.assertRaises(ValidationError):
            self.validator('Foo bar א')

    def test_too_long_does_not_raise_exception(self):
        self.validator('a' * 161)
