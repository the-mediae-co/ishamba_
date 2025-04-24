import itertools
import re
import phonenumbers
import sys
import logging
from string import Formatter
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.utils import formats
from django.utils.translation import gettext_lazy as _

from gateways import gateways, SMSGateway

from core.utils.clients import client_setting
from customers.models import Customer
from sms import constants
from world.models import Border, BorderLevelName
from world.utils import get_country_for_phone
from subscriptions.models import Subscription

import sentry_sdk

logger = logging.getLogger(__name__)

prog = None

sms_msg_matcher = re.compile(r'^[{}]+$'.format(constants.GSM_WHITELIST))


def clean_sms_text(text, message_count=1, strip=True):
    """ Checks for valid characters, and length, and trims whitespace and non-GSM characters. """
    gateway: SMSGateway = gateways.get_gateway(gateways.AT)
    try:
        return gateway.validate_long_message(text, max_sms_per_message=constants.MAX_SMS_PER_MESSAGE, strip=strip)
    except ValidationError as e:
        raise ValidationError({'text': e.message})


def validate_number(number, allow_international=False):
    """
    Validate that the given phone number is valid. If allow_international is False,
    we also ensure that the number is in one of the countries in which we operate.
    """
    if not allow_international:
        # Build a list of country codes for the countries that we operate in
        country_iso2s = BorderLevelName.objects.order_by('iso2').distinct('iso2').values_list('iso2', flat=True)
        country_codes = []
        for iso2 in country_iso2s:
            cc = next((key for key, val in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.items() if iso2 in val))
            if cc:
                country_codes.append(cc)
        kwargs = {'allowed_country_codes': country_codes}
        try:
            allowed_country = get_country_for_phone(number)
        except ValueError as e:
            # A value error is raised if the phone number is outside the countries that we operate in
            raise ValidationError(_('Not a country that we operate in.'))
    else:
        kwargs = {}
        allowed_country = None
    gateway = gateways.get_gateway(gateways.AT)
    validated = gateway.validate_recipients([str(number)],
                                            allowed_country=allowed_country,
                                            allow_international=allow_international,
                                            **kwargs)
    return len(validated) > 0


def prepare_numbers(numbers, allow_international: bool = False, to_string: bool = True):
    """
    Ensures numbers are all valid numbers, and returns them written in
    international (E164) format, optionally as a comma-separated string.

    Args:
        numbers: List of phonenumbers.phonenumber.PhoneNumber objects.
    """
    int_format = phonenumbers.PhoneNumberFormat.E164
    prepared_numbers = []
    failed_validation = []
    for number in numbers:
        formatted_number = phonenumbers.format_number(number, int_format)
        try:
            validate_number(number, allow_international=allow_international)
        except (ValueError, ValidationError):
            failed_validation.append(formatted_number)
        else:
            prepared_numbers.append(formatted_number)

    if to_string:
        prepared_numbers = ",".join(prepared_numbers)
        failed_validation = ",".join(failed_validation)
    return prepared_numbers, failed_validation


def get_i10n_template_text(template, language):
    from sms.models import SMSResponseTranslation
    try:
        return template.translations.get(language=language).text
    except (
        SMSResponseTranslation.DoesNotExist,
        SMSResponseTranslation.MultipleObjectsReturned,
    ):
        # If the customer's preferred language isn't available, try English
        t = template.translations.filter(language="eng")
        if t.exists():
            return t.first().text
        # If no English, see if there are any languages available
        t = template.translations.order_by("?").first()
        if t:
            msg = (f"get_i10n_template_text({template.id}) had to return {t.language} "
                   f"instead of customer's preference of {language}")
            sentry_sdk.capture_message(msg)
            logger.warning(msg)
            return t.text
        # Otherwise report an error and return nothing
        msg = (f"get_i10n_template_text({template.id}) had to return nothing "
               f"instead of customer's preference of {language}")
        sentry_sdk.capture_message(msg)
        logger.warning(msg)
        return None


def populate_templated_text(text: str, customer: Customer = None, end_date=None, voucher=None, context={}) -> str:
    """
    Returns the value of 'text', a text message formatted with a
    context dictionary assembled from the optional 'customer', 'end_date' and
    'voucher' kwargs.
    Not all message templates use all context variables, so
    missing data is to be expected in most uses, as e.g. we won't be supplying
    the 'voucher' kwarg unless we're formatting a voucher-related message
    template.
    """
    text_keys = [i[1] for i in Formatter().parse(text)]

    if 'short_end_date' in text_keys or 'long_end_date' in text_keys:
        try:
            # Get the end_date either as specified or from the customer. We'll only
            # be sending the subscription-ending or payment-received messages if
            # the customer already has a subscription.
            end_date = end_date or customer and customer.subscriptions.latest('end_date').end_date
        except Subscription.DoesNotExist:
            pass
    else:
        end_date = None

    # now we've had as many chances as we're going to get to specify an end_date
    if end_date is not None:
        short_end_date = formats.date_format(end_date, 'MONTH_DAY_FORMAT', use_l10n=True)
        long_end_date = formats.date_format(end_date, 'SHORT_DATE_FORMAT', use_l10n=True)
    else:
        short_end_date = ""
        long_end_date = ""

    voucher_duration = ""
    if 'voucher_duration' in text_keys:
        if voucher is not None:
            voucher_duration = voucher.offer.specific.months

    country_name = customer.border0.name if customer and customer.border0 else None

    context.update({
        'call_centre': format_phonenumber(client_setting('voice_queue_number', country_name=country_name)),
        'shortcode': client_setting('sms_shortcode', country_name=country_name),
        'till_number': client_setting('mpesa_till_number', country_name=country_name),
        'month_price': f"{client_setting('monthly_price',  country_name=country_name)} kshs",
        'year_price': f"{client_setting('yearly_price',  country_name=country_name)} kshs",
        'short_end_date': short_end_date,
        'long_end_date': long_end_date,
        'voucher_duration': voucher_duration,
    })
    return text.format(**context)


def _lcs(str1: str, str2: str):
    """
    Helper function to find the longest common substring of the two strings that are passed in.
    """
    pairs = zip(str1, str2)
    return ''.join(pair[0] for pair in itertools.takewhile(lambda pair: pair[0] == pair[1], pairs))


@lru_cache(maxsize=0 if "pytest" in sys.modules else 20)
def get_country_for_sender(sender: str) -> Border:
    gateway_settings = getattr(settings, 'GATEWAY_SETTINGS', [])
    for gateway_key in gateway_settings.keys():
        gateway_setting = gateway_settings.get(gateway_key)
        for entry in gateway_setting.get('senders', []):
            gw_country = entry.get('country')
            gw_senders = entry.get('senders')
            for gw_sender in gw_senders:
                if str(sender) == str(gw_sender):
                    return Border.objects.get(name=gw_country, level=0)
    return Border.objects.none()


def get_l10n_response_template_by_name(name: str, country: Border):
    from .models.keyword import SMSResponseTemplate

    l10n_name = name + f"_{country.name}" if country else name
    try:
        # First, assume the name is correct, without need for l10n
        template = SMSResponseTemplate.objects.get(name=name)
        return template
    except SMSResponseTemplate.DoesNotExist:
        # Try a localized template name
        # Use 'filter' instead of 'get' to avoid another exception
        templates = SMSResponseTemplate.objects.filter(name=l10n_name)
        if not templates:
            sentry_sdk.capture_message(f"No templates found: {name}, {country}")
            return None
        if templates.count() == 1:
            return templates.first()
        if templates.count() > 1:
            # Try to disambiguate the templates via country
            templates = SMSResponseTemplate.objects.filter(name=l10n_name).filter(
                Q(all_countries=True) | Q(countries=country)
            )
            return templates.first()
        return None
    except SMSResponseTemplate.MultipleObjectsReturned:
        # First try to retrieve a country-specific version
        # Use 'filter' instead of 'get' to avoid another exception
        templates = SMSResponseTemplate.objects.filter(name=name).filter(
            Q(all_countries=True) | Q(countries=country)
        )
        if templates.count() > 1:
            sentry_sdk.capture_message(f"Multiple country-specific empty message templates found")
        if templates:
            return templates.first()
        return None


def match_smsresponsekeyword_and_template(candidate_text: str, sender: Customer, *args, **kwargs):
    """
    Given a text string (e.g. keyword_text or incoming sms text string), retrieves the
    corresponding SMSResponseKeyword and SMSResponseTemplate objects, returning them
    if they exist. Otherwise, it returns None.

    The algorithm does a case-insensitive startswith keyword template DB search, using the
    first word of the candidate_text. Then it checks the resulting QuerySet to see which
    is the closest match (by length of matching substring). Finally, it checks whether the
    candidate_text string is more than twice as long as the template command. This is an
    arbitrary choice, but if it's too long, there is danger that this is a miss-recognition,
    so we opt for safety and return None.
    """
    # imported here to prevent circular imports
    from .models.keyword import SMSResponseKeyword

    if sender and sender.border0:
        sender_country = sender.border0
    else:
        sender_country = get_country_for_phone(sender.main_phone)

    if not candidate_text:
        # The empty SMS 'keyword' is a special case
        template = get_l10n_response_template_by_name(settings.SMS_EMPTY_MESSAGE_RESPONSE, sender_country)
        if not template:
            sentry_sdk.capture_message(f"Could not find empty message response template")
            return None, None
        if template.keywords.count() != 1:
            sentry_sdk.capture_message(f"Empty message response template has wrong number "
                                       f"of keywords: {template.keywords.count()}")
        return template.keywords.first(), template

    # Split the candidate_text and then strip the first word of any punctuation
    search_word = candidate_text.split()[0].strip(constants.GSM_WHITELIST_PUNCTUATION)

    try:
        # case-insensitive startswith search of the db, also returning the
        # corresponding response in the same DB query, sorted by keyword
        keyword_matches = SMSResponseKeyword.objects.prefetch_related('responses').filter(
            is_active=True,
            keyword__istartswith=search_word,
        ).filter(
            # Only consider keywords for templates that are active for this customer's country
            Q(responses__all_countries=True) | Q(responses__countries=sender_country),
        ).order_by('keyword')

        if not keyword_matches:
            return None, None

        # At this point, keyword_matches is a queryset of one or more keyword matches,
        # sorted by keyword, all starting with the common search_word beginning.
        longest_match_len, _, keyword = max(
            (len(_lcs(candidate_text, kw.keyword.upper())), i, kw)
            for i, kw in enumerate(keyword_matches)
        )

        if len(candidate_text) < 2 * longest_match_len:
            # We found a matching keyword. Find the corresponding response template for the
            # country that the sender is in, and then return the keyword and template.
            template = keyword.responses.filter(
                Q(all_countries=True) | Q(countries=sender_country)
            )
            if template.count() == 1:
                return keyword, template.first()
            else:
                sentry_sdk.capture_message(f"WARNING: Wrong number of templates found: {candidate_text}, {sender.main_phone}, {template.count()}")
                # No match, or multiple matches, requires a CCA to handle until we clear the duplicate
                return None, None

        return None, None  # if no match for the heuristic, return None

    except ObjectDoesNotExist:  # on error, return None
        return None, None


# wrapper for get_populated_sms_templates_text_and_task() which ignores the create_task param.
# Eventually all uses of this should be removed and replaced with some common code that would
# check and create the task if necessary.
def get_populated_sms_templates_text(
    template_name: str,
    customer: Customer,
    end_date=None,
    voucher=None,
    context=None,
    skip_formatting: bool = False
) -> tuple[str, str]:
    """
    Retrieves and renders template by name. Raises DoesNotExist exception if template is not found.
    Optional keyword arguments are used to provide additional context for rendering the template.
    """
    text, sender, _ = get_populated_sms_templates_text_and_task(
        template_name, customer, end_date, voucher, context, skip_formatting
    )
    return text, sender


def get_populated_sms_templates_text_and_task(
    template_name: str,
    customer: Customer,
    end_date=None,
    voucher=None,
    context=None,
    skip_formatting=False
) -> tuple[str, str, bool]:
    """
    Retrieves and renders template by name. Raises DoesNotExist exception if template is not found.
    Optional keyword arguments are used to provide additional context for rendering the template.
    Returns a tuple of (message text, the sender to use, whether to create a task)
    """
    context = {} if context is None else context
    # Prevent circular import issues
    from sms.models import SMSResponseTemplate
    if customer is None or customer.border0 is None:
        sentry_sdk.capture_message(f"WARNING: get_populated_sms_templates_text_and_task called with no customer or border")
        kenya = Border.objects.get(name='Kenya', level=0)
        response_template = get_l10n_response_template_by_name(template_name, kenya)
    else:
        response_template = get_l10n_response_template_by_name(template_name, customer.border0)
    if not response_template:
        raise SMSResponseTemplate.DoesNotExist

    # Get the preferred language response text for this customer.
    text = get_i10n_template_text(response_template, customer.preferred_language)

    if skip_formatting:
        return text, response_template.sender, response_template.action == SMSResponseTemplate.Actions.TASK

    return (populate_templated_text(text,
                                    customer=customer,
                                    end_date=end_date,
                                    voucher=voucher,
                                    context=context),
            response_template.sender,
            response_template.action == SMSResponseTemplate.Actions.TASK)


def format_phonenumber(number):
    number = phonenumbers.parse(number)
    national_format = getattr(phonenumbers.PhoneNumberFormat, 'NATIONAL')
    formatted = phonenumbers.format_number(number, national_format)
    return re.sub(' ', '', formatted)


def validate_sms(msg, check_len=False):
    """
    Validates that the content of msg only contains characters
    within the GSM character set.
    If the `check_len` kwarg is set then the length of the message will also be
    checked against `sms.constants.MAX_SMS_LEN`.
    """
    if check_len:
        if len(msg) > constants.MAX_SMS_LEN:
            return False

    global sms_msg_matcher
    return sms_msg_matcher.match(msg)
