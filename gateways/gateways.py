from __future__ import annotations

import logging
import re
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Any, List, Optional, Union

if TYPE_CHECKING:
    from sms.models import OutgoingSMS

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

import phonenumbers
import sentry_sdk

from core.validators import GSMCharacterSetValidator
from sms.constants import GSM_EXTENDED_SET, GSM_WHITELIST

logger = logging.getLogger(__name__)

__all__ = ['Gateway', 'SMSGateway', 'gateways', 'get_gateway']


class Gateways(object):
    """ Registry of all supported gateways. """

    def __init__(self):
        # Internal registry of gateways
        self._gateways = {}

        # Django-style options list for providing model / form choices
        # e.g. [(0, 'Foo'), (1, 'bar')]
        self.GATEWAY_CHOICES = []

    def register_gateway(self, gateway):
        """
        Registers a Gateway.

        Args:
            gateway: Gateway sub-class (with gateway.Meta defined).
        """
        gateway_id = gateway.Meta.gateway_id
        self._gateways[gateway_id] = gateway

        setattr(self, gateway.Meta.short_name.upper(), gateway_id)
        self.GATEWAY_CHOICES.append((gateway_id, gateway.Meta.verbose_name))

    def get_gateway_cls(self, gateway_id: int):
        try:
            return self._gateways[gateway_id]
        except KeyError:
            raise LookupError(
                "'%d' doesn't correspond to a registered Gateway" % gateway_id)

    @lru_cache(maxsize=None)
    def get_gateway(self, gateway_id: int, **kwargs):
        return self.get_gateway_cls(gateway_id)(**kwargs)


#: Registry of all supported gateways.
gateways = Gateways()


def get_gateway(gateway):
    """
    Returns an initialised gateway based on the passed gateway identifier.
    """
    warnings.warn(
        "The get_gateway() function is deprecated. Use the "
        "gateways.get_gateway() instead.", stacklevel=2
    )
    return gateways.get_gateway(gateway)


class GatewayBase(type):
    """ Metaclass for all Gateways. """

    def __new__(cls, name, bases, attrs):
        """
        Register gateways when constructing 'leaf-node' subclasses of Gateway.
        """
        new_cls = super(GatewayBase, cls).__new__(cls, name, bases, attrs)

        # We only register Gateways for which we provide a nested Meta
        # class.
        if hasattr(new_cls, 'Meta'):
            gateways.register_gateway(new_cls)
        return new_cls


class Gateway(metaclass=GatewayBase):
    """
    Base object for sub-classing to support specific gateways.

    Specific gateway implementations should define a nested Meta class in the
    following format:

    class Meta:
        gateway_id = 0
        short_name = 'AT'
        verbose_name = 'AfricasTalking'
    """
    TIMEOUT = 30
    DEFAULT_SENDER = None

    default_error_messages = {
        'message_blank': _("Message blank"),
    }

    def __init__(self, error_messages: Optional[dict] = None, *args, **kwargs):
        """
        Keyword Args:
            error_messages: An optional dictionary to override the default
                error messages that the gateway will raise.
        """

        # Build the error_messages dictionary including parent class messages
        # and error_messages if given.
        messages = {}
        for c in reversed(self.__class__.__mro__):
            messages.update(getattr(c, 'default_error_messages', {}))
        messages.update(error_messages or {})
        self.error_messages = messages

    def _get_secrets(self, alias: str = 'default') -> dict:
        """
        Returns:
            Dict. Secrets dictionary for the gateway.

        Example:
            GATEWAY_SECRETS = {
                'AT': {
                    'default': {
                        'username': None
                        'api_key': None,
                        'sender': None,
                    }
                }
            }
            E.g. self._get_secrets(alias='default')
            {
                'username': None
                'api_key': None,
                'sender': None,
            }
        """
        if not hasattr(self, 'Meta'):
            raise NotImplementedError(
                "Non-leaf node classes don't have settings")

        # check GATEWAY_SECRETS setting is defined
        secrets_dict = getattr(settings, 'GATEWAY_SECRETS', None)
        if secrets_dict is None:
            raise ImproperlyConfigured('Missing GATEWAY_SECRETS setting.')

        try:
            return secrets_dict[self.Meta.short_name][alias]
        except KeyError:
            raise ImproperlyConfigured('Incorrectly configured GATEWAY_SECRETS setting.')

    def _get_settings(self, gateway_name: Optional[str] = None) -> dict:
        """
        Returns:
            Dict. Settings dictionary for the gateway.

        Example:
            GATEWAY_SETTINGS = {
                'AT': {
                    'senders': [
                        {
                            'country': 'Kenya',
                            'senders': [21606, 'iShambaK']
                        },
                        {
                            'country': 'Uganda',
                            'senders': ['iShambaU']
                        },
                    ]
                }
            }

        If 'gateway_name' is defined, return the settings associated with that gateway. Otherwise,
        return the settings associated with the Meta setting for self.
        If neither gateway_name nor the Meta gateway name are defined, return the whole settings dict.
        """
        if not hasattr(self, 'Meta'):
            raise NotImplementedError(
                "Non-leaf node classes don't have settings")

        # check GATEWAY_SETTINGS setting is defined
        settings_dict = getattr(settings, 'GATEWAY_SETTINGS', None)
        if settings_dict is None:
            raise ImproperlyConfigured('Missing GATEWAY_SECRETS setting.')

        if self.Meta.short_name and not gateway_name:
            gateway_name = self.Meta.short_name

        try:
            if not gateway_name:
                return settings_dict
            else:
                return settings_dict[gateway_name]
        except KeyError:
            raise ImproperlyConfigured(f'Incorrectly configured GATEWAY_SETTINGS setting: {gateway_name}.')

    @staticmethod
    def get_sender_choices(country_names: Optional[list[str]] = None) -> list[tuple[str, str]]:
        """
        Returns a set of sender choices in the format of the django ChoiceField choices.
        https://docs.djangoproject.com/en/4.0/ref/models/fields/#field-choices
        """
        gateway_settings = getattr(settings, 'GATEWAY_SETTINGS', {})

        sender_choices = []

        for gateway_short_name in gateway_settings.keys():
            gw = gateway_settings[gateway_short_name]
            for sender_details in gw.get('senders'):
                country = sender_details.get('country')
                senders = sender_details.get('senders')
                if country_names is None or country in country_names:
                    # Build list of options of the form (sender, 'sender (country)')
                    sender_choices.extend(map(lambda s: (s, str(s) + f' ({country})'), senders))

        # Remove duplicates
        sender_choices = list(set(sender_choices))
        if len(sender_choices) > 1:
            # Sort by sender. The above check prevents an error if GATEWAY_SETTINGS is not found
            sender_choices.sort(key=lambda x: str(x[0]))
        return sender_choices

    def get_customer_filter_kwargs(self):
        raise NotImplementedError("get_customer_filter_kwargs must be defined in subclasses")

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        return queryset.filter(
            **self.get_customer_filter_kwargs()
        )


class SMSGateway(Gateway):
    """
    Base class for SMS gateways providing common validation functionality.
    """
    MESSAGE_MAX_LEN = 160
    # minimum message length allowed when splitting messages
    MIN_MESSAGE_LEN = 2

    MAX_SMS_PER_MESSAGE = 2
    PAGINATION_FORMAT = ' ({:d}/{:d})'
    SMS_PAGINATION_OFFSET = len(PAGINATION_FORMAT.format(MAX_SMS_PER_MESSAGE,
                                                         MAX_SMS_PER_MESSAGE))
    RECIPIENT_BATCH_SIZE = 1000

    default_error_messages = {
        'message_too_long': _("Message is too long for a single SMS but "
                              "does not include break points."),
        'message_invalid_characters': _("Message contains invalid (non-GSM) "
                                        "characters: "),
        'duplicate_recipients': _("The list of recipients contains "
                                  "duplicates"),
        'invalid_recipient': _("%(phone_number)s is not a valid recipient"),
        'invalid_recipient_country': _("%(recipient_phone)s is not in an "
                                       "allowed recipient country "
                                       "(%(valid_country)s)"),
        'invalid_recipient_countrycode': _("%(recipient_code)s is not an "
                                           "allowed recipient country code. Allowed: "
                                           "(%(valid_codes)s)"),
        'message_requires_too_many_sms': _(
            "Sending would require more than the maximum number of SMS per "
            "message (%(max_sms_per_message)d)."),
    }
    gateway_kwargs = {}

    def send_message(self, message: OutgoingSMS, recipient_ids: Union[QuerySet, list[int]], **kwargs: Any):
        raise NotImplementedError("send_message")

    def validate_message(self, msg: str, strip: bool = True) -> str:
        """
        Validates the given message stripping white-space and non-GSM characters by default.

        Args:
            msg: The message to be validated
            strip: Whether or not to strip white-space AND non-GSM characters.

        Returns:
            str. Valid message (with white-space stripped).

        Raises:
            ValidationError: When a message does not meet validation
                requirements.
        """
        if strip:
            msg = self.strip_non_gsm(msg)

        msg_len = len(msg)

        if msg_len == 0:
            raise ValidationError(self.error_messages['message_blank'])

        # The GSM extended set characters take one additional character slot each
        extended_count = len(re.findall(r'[' + re.escape(GSM_EXTENDED_SET) + r']',  msg))

        if len(msg) + extended_count > self.MESSAGE_MAX_LEN:
            raise ValidationError(self.error_messages['message_too_long'])

        try:
            GSMCharacterSetValidator()(msg)
        except ValidationError:
            raise ValidationError(
                self.error_messages['message_invalid_characters'] + msg)

        return msg

    def validate_recipients(self, recipients: list[str],
                            allowed_country=None,
                            allow_duplicates: bool = False,
                            allowed_country_codes: Optional[list[int]] = None,
                            allow_international: bool = False) -> list[str]:
        """
        Validates the given list of recipients.

        Args:
            recipients: list of recipients to validate.
            allowed_country: Border object of country that this sender can send to. If None, no check is made.
            allow_duplicates: Whether to allow duplicate
            allowed_country_codes: list(int) of allowed international country
                codes.
            allow_international: Whether to allow international recipients (those outside the allowed country codes)
        """
        from world.utils import get_phone_country_code_for_country

        # Check for duplicates
        if not allow_duplicates and len(set(recipients)) != len(recipients):
            raise ValidationError(self.error_messages['duplicate_recipients'])

        E164 = phonenumbers.PhoneNumberFormat.E164

        try:
            # Ensure that all phone numbers are valid
            phones = list(map(lambda n: phonenumbers.parse(n, None), recipients))
            invalid_numbers = map(lambda p: phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
                                  if not phonenumbers.is_valid_number(p) else None, phones)
            # Don't validity-check the temporary fake '+245' phone numbers used for duplicate farmers
            invalid_numbers = [x for x in invalid_numbers if x is not None and not x.startswith('+245')]
            if invalid_numbers:
                invalid_numbers = list(invalid_numbers)
                sentry_sdk.capture_message(f"bulk_sms: invalid recipients {invalid_numbers}")
                raise ValidationError(self.error_messages['invalid_recipient'] % {'phone_number': invalid_numbers})
        except phonenumbers.NumberParseException as e:
            sentry_sdk.capture_message(f"bulk_sms: invalid recipient {e}")
            raise ValidationError(self.error_messages['invalid_recipient'] % {'phone_number': e})

        if allowed_country and not allow_international:
            # Validate that the recipients are all from the allowed country
            # First, get the phone number country code
            cc = get_phone_country_code_for_country(allowed_country)
            if allowed_country_codes and cc not in allowed_country_codes:
                msg = f"The allowed country for {allowed_country} ({cc}) is not in " \
                      f"the allowed country codes {allowed_country_codes}"
                sentry_sdk.capture_message(msg)
                raise ImproperlyConfigured(msg)

            ccs = set(map(lambda p: p.country_code, phones))
            invalid_ccs = list(filter(lambda c: c != cc, ccs))
            # Don't validity-check the temporary fake '+245' phone numbers used for duplicate farmers
            invalid_ccs = [x for x in invalid_ccs if x != 245]
            if invalid_ccs:
                msg = self.error_messages['invalid_recipient_countrycode'] % {'recipient_code': invalid_ccs, 'valid_codes': cc}
                sentry_sdk.capture_message(msg)
                raise ValidationError(msg)

            formatted_numbers = list(map(lambda p: phonenumbers.format_number(p, E164), phones))
        else:
            formatted_numbers = list(
                map(lambda p: phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164), phones)
            )

        return formatted_numbers


    def strip_non_gsm(self, msg: str) -> str:
        msg = msg.strip()  # Strip whitespace
        regex = '[^{}]'.format(re.escape(GSM_WHITELIST + GSM_EXTENDED_SET))
        return re.sub(regex, '', msg)  # Strip non-GSM characters

    def validate_long_message(self, msg: str, strip=True,
                              max_sms_per_message: Optional[int] = None,
                              paginate: bool = True) -> str:
        """
        Validate message by splitting it and validating each part.
        """
        if max_sms_per_message is None:
            max_sms_per_message = self.MAX_SMS_PER_MESSAGE
        if strip:
            msg = self.strip_non_gsm(msg)
        pages = self.split_text_into_pages(msg, paginate=paginate)
        if len(pages) > max_sms_per_message:
            raise ValidationError(
                self.error_messages['message_requires_too_many_sms'],
                params={'max_sms_per_message': max_sms_per_message})
        for page in pages:
            self.validate_message(page, strip=strip)
        return msg

    def split_text_into_pages(self, text: str, limit: int = MESSAGE_MAX_LEN,
                              break_on: str = '\n', paginate: bool = True) -> List[str]:
        """
        Packs a given string into the fewest number of messages

        Args:
            text: str
            limit: int character limit for each message
            break_on: str to use if the message needs to be split
            paginate: If True message page suffixes will be added, e.g., (1/2)

        Returns:
            A list of strings representing the individual messages to be sent
        """
        len_txt = len(text)

        extended_regex = r'[' + re.escape(GSM_EXTENDED_SET) + r']'
        # The GSM extended set characters take one additional character slot each
        extended_count = len(re.findall(extended_regex,  text))

        if len_txt + extended_count <= limit:
            return [text.replace(break_on, ' ')]

        if paginate:
            limit -= self.SMS_PAGINATION_OFFSET

        messages = []
        offset = 0
        while offset < len_txt:
            end = offset + limit
            chunk = text[offset:end]
            chunk_regex_count = len(re.findall(extended_regex,  chunk))
            # If there's a GSM Extended set character in the chunk, shorten
            # the chunk length because they take extra space in encoding.
            if chunk_regex_count:
                end -= chunk_regex_count
                chunk = text[offset:end]
            last_break = self.find_break(chunk, break_on)
            if last_break != -1 and end < len_txt:
                # Shrink chunk, replace break, and move offset
                chunk = chunk[:last_break]
                offset += last_break + 1
            else:
                offset += limit
            chunk = chunk.replace(break_on, ' ')
            messages.append(chunk.strip())

        if paginate:
            paged = []
            total = len(messages)
            for idx, message in enumerate(messages, start=1):
                pages = self.PAGINATION_FORMAT.format(idx, total)
                paged.append(message + pages)
            messages = paged

        return messages

    def find_break(self, chunk: str, break_on: str) -> int:
        """
        Find the best break point in a given chunk, giving priority to the break_on string,
        then to space after end of sentence, then to any space.
        NOTE: Sentence pagination was disabled because it created too many pages when
        short sentences are being sent.
        Returns offset within chunk, or -1 if no good break could be found.
        """
        offset = chunk.rfind(break_on)
        # if offset < self.MIN_MESSAGE_LEN:
        #     offset = chunk.rfind('. ') + 1  # we want to break after the period, thus +1
        if offset < self.MIN_MESSAGE_LEN:
            offset = chunk.rfind(' ')
        if offset < self.MIN_MESSAGE_LEN:
            offset = -1

        return offset
