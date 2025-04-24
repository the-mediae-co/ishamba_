import warnings
from unittest import skip

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import override_settings
from django.test.utils import isolate_lru_cache

from gateways import Gateway, SMSGateway, gateways, get_gateway

from world.models import Border
from world.utils import get_phone_country_code_for_country

from core.test.cases import TestCase


class GetGatewaysTestCase(TestCase):
    def test_get_AT_warns_about_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            get_gateway(gateways.AT)

            self.assertEqual(len(w), 1)


class SMSGatewayMessageValidationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.gateway = SMSGateway()

    def test_valid_message_with_no_whitespace_returned_unmodified(self):
        msg = "This is a valid message."
        result = self.gateway.validate_message(msg)
        self.assertEqual(msg, result)

    def test_valid_message_with_whitespace_returned_modified(self):
        msg = "This is a valid message. "
        result = self.gateway.validate_message(msg)
        self.assertEqual(msg[:-1], result)

    def test_valid_message_with_whitespace_returned_unmodified_when_strip_disabled(self):
        msg = "This is a valid message. "
        result = self.gateway.validate_message(msg, strip=False)
        self.assertEqual(msg, result)

    def test_blank_messages_raises_validation_error(self):
        expected_msg = str(self.gateway.error_messages['message_blank'])
        with self.assertRaisesMessage(ValidationError, expected_msg):
            msg = ""  # blank
            self.gateway.validate_message(msg)

    def test_message_above_length_raises_validation_error(self):
        msg_len = self.gateway.MESSAGE_MAX_LEN + 1
        msg = "A" * msg_len
        expected_err_msg = self.gateway.error_messages['message_too_long'] % {
            'msg_len': msg_len,
            'max_len': self.gateway.MESSAGE_MAX_LEN}
        with self.assertRaisesMessage(ValidationError, expected_err_msg):
            self.gateway.validate_message(msg)

    def test_long_message_validation(self):
        msg_len = self.gateway.MESSAGE_MAX_LEN * 3 + 1
        msg = 'A' * msg_len
        expected_err_msg = self.gateway.error_messages['message_requires_too_many_sms'] % {
            'max_sms_per_message': 3}
        with self.assertRaisesMessage(ValidationError, expected_err_msg):
            self.gateway.validate_long_message(msg, max_sms_per_message=3)
        self.gateway.validate_long_message(msg, max_sms_per_message=4)

    def test_invalid_character_raises_validation_error(self):
        msg = "ƿƿƿ"
        expected_err_msg = str(self.gateway.error_messages['message_invalid_characters'])
        with self.assertRaisesMessage(ValidationError, expected_err_msg):
            self.gateway.validate_message(msg, strip=False)

    def test_invalid_character2_raises_validation_error(self):
        msg = 'In the month of JANUARY, Turkana county is likely to be mostly sunny and dry. ' \
               'The temperatures are likely to be high with a range of 30°C - 40°C - Kenya Met.'
        expected_err_msg = str(self.gateway.error_messages['message_invalid_characters'])
        with self.assertRaisesMessage(ValidationError, expected_err_msg):
            self.gateway.validate_message(msg, strip=False)

    def test_invalid_character_raises_long_message_validation_error(self):
        msg = "ƿƿƿ"
        expected_err_msg = str( self.gateway.error_messages['message_invalid_characters'])
        with self.assertRaisesMessage(ValidationError, expected_err_msg):
            self.gateway.validate_long_message(msg, strip=False)

    def test_invalid_message_strips_non_gsm(self):
        invalid_msg = 'In the month of JANUARY, Turkana county is likely to be mostly sunny and dry. ' \
                      'The temperatures are likely to be high with a range of 30°C - 40°C - Kenya Met.'
        valid_msg = 'In the month of JANUARY, Turkana county is likely to be mostly sunny and dry. ' \
                    'The temperatures are likely to be high with a range of 30C - 40C - Kenya Met.'
        self.assertEqual(valid_msg, self.gateway.validate_message(invalid_msg, strip=True))


class SMSGatewayRecipientValidationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.gateway = SMSGateway()
        self.kenya = Border.objects.get(country='Kenya', level=0)

    def test_valid(self):
        before = ['+254700000001']
        after = self.gateway.validate_recipients(before, allowed_country=self.kenya)
        self.assertEqual(before, after)

    def test_accepts_fake_245_countrycode_recipients(self):
        before = ['+2457000000001']
        after = self.gateway.validate_recipients(before, allowed_country=self.kenya)
        self.assertEqual(before, after)

    def test_raises_ValidationError_for_invalid_recipients(self):
        numbers = ['+2547000000001']
        expected_msg = self.gateway.error_messages['invalid_recipient'] % {
            'phone_number': numbers
        }
        with self.assertRaisesMessage(ValidationError, expected_msg):
            self.gateway.validate_recipients(numbers, allowed_country=self.kenya)

    def test_raises_ValidationError_for_duplicate_recipients(self):
        numbers = ['+254700000001', '+254700000001']
        expected_msg = str(self.gateway.error_messages['duplicate_recipients'])
        with self.assertRaisesMessage(ValidationError, expected_msg):
            self.gateway.validate_recipients(numbers, allowed_country=self.kenya)

    def test_does_not_raise_ValidationError_for_duplicate_recipients_when_allowed(self):
        numbers = ['+254700000001', '+254700000001']
        self.gateway.validate_recipients(numbers, allow_duplicates=True, allowed_country=self.kenya)

    def test_raises_ValidationError_for_invalid_country_codes(self):
        numbers = ['+447700000001']
        valid_codes = [254, 256]
        allowed_country = self.kenya
        cc = get_phone_country_code_for_country(allowed_country)
        expected_msg = self.gateway.error_messages['invalid_recipient_countrycode'] % {
            'recipient_code': [44],
            'valid_codes': cc
        }
        with self.assertRaisesMessage(ValidationError, expected_msg):
            self.gateway.validate_recipients(numbers,
                                             allowed_country_codes=valid_codes,
                                             allowed_country=allowed_country)

    def test_does_not_raise_ValidationError_for_valid_country_codes(self):
        numbers = ['+254700000001', '+256700000001']
        valid_codes = [254, 256]
        self.gateway.validate_recipients(numbers,
                                         allowed_country_codes=valid_codes,
                                         allowed_country=None)


class SMSGatewaySplitTextIntoMessagesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.gateway = SMSGateway()

    def test_compose_sms_single(self):
        text = "This is a short message"
        self.assertEqual(self.gateway.split_text_into_pages(text), [text])

    def test_compose_sms_single_with_breaks(self):
        text = "This is a short message.\nBut it still has multiple parts."
        expected = "This is a short message. But it still has multiple parts."
        self.assertEqual(self.gateway.split_text_into_pages(text), [expected])

    @skip("Message pagination on sentence boundaries is disabled.")
    def test_compose_sms_multiple_no_breaks_with_period(self):
        txt = ("This is a long message without any breaks in the text to help "
               "the compose code decide how to split it into sensible chunks. "
               "It is so long that I have run out of things to say in this "
               "pretend message.")

        expected = [
            ("This is a long message without any breaks in the text to help "
             "the compose code decide how to split it into sensible chunks."),
            ("It is so long that I have run out of things to say in this "
             "pretend message."),
        ]

        output = self.gateway.split_text_into_pages(txt, paginate=False)
        self.assertEqual(output, expected)

    def test_compose_sms_multiple_no_breaks_no_period(self):
        txt = ("This is a long message without any breaks in the text to help "
               "the compose code decide how to split it into sensible chunks, and "
               "also with no sentence period which makes it tougher yet to split")
        expected = [
            ('This is a long message without any breaks in the text to help '
             'the compose code decide how to split it into sensible chunks, and '
             'also with no sentence period'),
            'which makes it tougher yet to split']

        output = self.gateway.split_text_into_pages(txt, paginate=False)
        self.assertEqual(output, expected)

    def test_compose_sms_multiple_no_pages_with_break(self):
        txt = ("This is a long message without any breaks in the text to help "
               "the compose code decide how to split it into sensible\nchunks. "
               "It is so long that I have run out of things to say in this "
               "pretend message.")

        expected = [
            ("This is a long message without any breaks in the text to help "
             "the compose code decide how to split it into sensible"),
            ("chunks. It is so long that I have run out of things to say in this "
             "pretend message."),
        ]

        output = self.gateway.split_text_into_pages(txt, paginate=False)
        self.assertEqual(output, expected)

    def test_compose_sms_multiple_with_break(self):
        txt = ("This is a long message without any breaks in the text to help "
               "the compose code decide how to split it into sensible chunks.\n"
               "It is so long that I have run out of things to say in this "
               "pretend message.")

        expected = [
            ("This is a long message without any breaks in the text to help "
             "the compose code decide how to split it into sensible chunks. "
             "(1/2)"),
            ("It is so long that I have run out of things to say in this "
             "pretend message. (2/2)"),
        ]

        self.assertEqual(self.gateway.split_text_into_pages(txt), expected)

    def test_compose_sms_multiple_with_unnecessary_break(self):
        # note that first break is necessary, but second one is not, since the rest can fit in the second message
        parts = ['a' * 150, 'b' * 20, 'c' * 20]
        txt = '\n'.join(parts)
        expected = [parts[0], ' '.join(parts[1:])]
        self.assertEqual(self.gateway.split_text_into_pages(txt, paginate=False), expected)

    def test_compose_sms_multiple_with_many_breaks(self):
        part = f'{"a" * 15}\n'
        txt = (part * 22).strip()
        # 16 characters per part with break, 22 parts = 3 SMS messages
        sms12 = (part * 10).replace('\n', ' ').strip()
        sms3 = (part * 2).replace('\n', ' ').strip()
        expected = [sms12, sms12, sms3]
        parts = self.gateway.split_text_into_pages(txt, paginate=False)
        self.assertEqual(3, len(parts))
        self.assertEqual(expected, parts)


class GatewaysRegisteryTestCase(TestCase):
    def test_AT_registered(self):
        self.assertEqual(getattr(gateways, 'AT'), 0)

    def test_get_default_gateway_AT(self):
        with isolate_lru_cache(gateways.get_gateway):
            gw = gateways.get_gateway(gateways.AT)
            self.assertEqual(
                gw.api_key,
                settings.GATEWAY_SECRETS['AT']['default']['api_key'])

    @override_settings(GATEWAY_SECRETS=None)
    def test_get_gateway_no_config(self):
        with isolate_lru_cache(gateways.get_gateway):
            with self.assertRaisesMessage(ImproperlyConfigured,
                                          'Missing GATEWAY_SECRETS setting'):
                gateways.get_gateway(gateways.AT)

    @override_settings(GATEWAY_SECRETS={'AT': {'malformed': True}})
    def test_get_gateway_missing_alias_rasies_ImproperlyConfigured(self):
        expected_msg = 'Incorrectly configured GATEWAY_SECRETS setting.'
        with isolate_lru_cache(gateways.get_gateway):
            with self.assertRaisesMessage(ImproperlyConfigured, expected_msg):
                gateways.get_gateway(gateways.AT)

    @override_settings(GATEWAY_SECRETS={'AT': {'default': {'username': 'ex', 'api_key': 'key'}}})
    @skip("sender does not seem to be validated anymore")
    def test_get_gateway_missing_alias_property_raises_ImproperlyConfigured(self):
        """ Test with missing 'sender' alias prop """
        with isolate_lru_cache(gateways.get_gateway):
            with self.assertRaises(ImproperlyConfigured):
                gateways.get_gateway(gateways.AT)

    def test_get_gateway_invalid_gateway_id(self):
        gid = -1
        expected_msg = "'%d' doesn't correspond to a registered Gateway" % gid

        with isolate_lru_cache(gateways.get_gateway):
            with self.assertRaisesMessage(LookupError, expected_msg):
                gateways.get_gateway(gid)

    def test_non_leaf_node_get_secrets(self):
        with self.assertRaises(NotImplementedError):
            SMSGateway()._get_secrets()


class SMSGatewaySettingsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.gateway = gateways.get_gateway(0)

    def test_get_settings(self):
        gw_settings = self.gateway._get_settings()
        self.assertIsInstance(gw_settings, dict)
        self.assertTrue(gw_settings.get('senders'))
        gw_settings = self.gateway._get_settings(gateway_name='AT')
        self.assertTrue(gw_settings.get('senders'))

    def test_get_sender_choices(self):
        choices = Gateway.get_sender_choices()
        self.assertIsInstance(choices, list)
        self.assertEqual(3, len(choices))
        self.assertEqual(2, len(choices[0]))

        choices = Gateway.get_sender_choices(['Kenya'])
        self.assertIsInstance(choices, list)
        self.assertEqual(2, len(choices))
        self.assertEqual(2, len(choices[0]))
