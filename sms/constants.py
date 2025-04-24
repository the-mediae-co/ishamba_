from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

MAX_SMS_LEN = 160
MAX_SMS_PER_MESSAGE = 3
PAGINATION_FORMAT = ' ({:d}/{:d})'
SMS_PAGINATION_OFFSET = len(PAGINATION_FORMAT.format(MAX_SMS_PER_MESSAGE,
                                                     MAX_SMS_PER_MESSAGE))

KENYA_COUNTRY_CODE = 254
UGANDA_COUNTRY_CODE = 256
ZAMBIA_COUNTRY_CODE = 260

AT_BATCH_SIZE = 5000
AT_ENQUEUE_THRESHOLD = 100

# Used for SMS tests
SMS_API_IPS = settings.AUTHORIZED_IPS

# Characters from the GSM character set extension require two septets to encode (escape + char)
# https://en.wikipedia.org/wiki/GSM_03.38#GSM_7-bit_default_alphabet_and_extension_table_of_3GPP_TS_23.038_.2F_GSM_03.38
# See also: http://www.unicode.org/Public/MAPPINGS/ETSI/GSM0338.TXT
# Technically CR2 and SS2 are part of the GSM extended set, but they appear to not be used so we don't include them
GSM_EXTENDED_SET = '^{}\\|[]~€\f'  # \f is form feed (FF)

# All other GSM characters require one septet to encode
GSM_WHITELIST_PUNCTUATION = '!# "%&\'()*,.?+-/;:<=>¡¿_@'
GSM_WHITELIST = (
    # thanks to http://stackoverflow.com/a/10359172
    # Standard Latin characters
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    'abcdefghijklmnopqrstuvwxyz'
    # Numbers
    '0123456789'
    # Currency
    '$£¥\u00A4'
    # Accented Characters
    'èéùìòÇØøÆæßÉÅåÄÖÑÜ§äöñüà'
    # Technically the spec includes 'Ç' instead of 'ç', however modern implementations are encouraged to use the lower case
    # http://www.unicode.org/Public/MAPPINGS/ETSI/GSM0338.TXT
    'ç'
    # Greek Characters
    '\u0394\u03A6\u0393\u039B\u03A9\u03A0\u03A8\u03A3\u0398\u039E'
    # Escape, newline, carriage return
    '\u001B\n\r'
) + GSM_WHITELIST_PUNCTUATION

RESPOND_TO_JOIN_TASK_TITLE = ("Enroll new customer")
RESPOND_TO_UNPARSABLE_SMS_TASK_TITLE = (
    "Respond to SMS")
RESPOND_TO_PAYMENT_TASK_TITLE = (
    "Respond to payment error from customer")
REVIEW_RESPONSE_TASK_TITLE = ("Review customer's response to our query")

VANILLA_SMS_DETAILS_TEMPLATE = "SMS from customer:\n\n> {text}"
KEYWORD_SMS_DETAILS_TEMPLATE = ("SMS from customer:\n\n"
                                "> {text}\n\n"
                                "Matched '{keyword}' keyword. "
                                "'{response_name}' response sent."
                                )

RESPOND_TO_AI_ERROR_TASK_TITLE = "AI Signup agent requires human intervention"

FREE_MONTHS = 1  # for new customers


SUBSCRIPTION_ENDING_WARNING_PERIODS = {
    settings.SMS_SUBSCRIPTION_REMINDER: 4,
    settings.SMS_SUBSCRIPTION_EXPIRED: -1,  # i.e. 'yesterday'
}


class Actions(models.TextChoices):
    NONE = 'none', _('No Action')
    TASK = 'task', _('Create Task')
    JOIN = 'join', _('Join Customer')
    STOP = 'stop', _('Stop Customer')


class OUTGOING_SMS_TYPE(models.TextChoices):
    UNKNOWN = "?",  "Unknown"
    BULK = "bulk", "Bulk"  # A bespoke message sent to many customers
    INDIVIDUAL = "one", "Individual"  # A bespoke message sent to one customer
    TASK_RESPONSE = "task", "Task Response"  # An agent's response to a task
    TEMPLATE_RESPONSE = "auto" , "Template Response" # An auto-response to an incoming sms matching a template
    NEW_CUSTOMER_RESPONSE = "new", "New Customer Response"  # An auto-response sent to new customers requesting to register
    NPS_REQUEST = "nps", "Nps Request"
    AGRI_TIP = "tip", "Agr Tip"  # An AtriTip series message
    WEATHER_KENMET = "wxke", "Weather Kenmet"  # Distinguish between KenMET and PlantVillage
    WEATHER_PLANTVILLAGE = "wxpv", "Weather PlantVillage"
    MARKET_PRICE = "mkt", "Market Price"
    SUBSCRIPTION_NOTIFICATION = "sub", "Subscription Notification"  # Historical
    VOUCHER = "vchr", "Voucher"  # Historical
    WEATHER_AND_MARKET = "wxmkt", "Weather and Market"  # Historical
    DATA_REQUEST = "query", "Data Request"


SMS_TYPE_ICON_MAP  = {
    OUTGOING_SMS_TYPE.UNKNOWN: "question",
    OUTGOING_SMS_TYPE.BULK: "envelopes-bulk",
    OUTGOING_SMS_TYPE.INDIVIDUAL: "envelope",
    OUTGOING_SMS_TYPE.TASK_RESPONSE: "list-check",
    OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE: "robot",
    OUTGOING_SMS_TYPE.NEW_CUSTOMER_RESPONSE: "person-circle-plus",
    OUTGOING_SMS_TYPE.NPS_REQUEST: "gavel",
    OUTGOING_SMS_TYPE.DATA_REQUEST: "clipboard-question",
    OUTGOING_SMS_TYPE.AGRI_TIP: "graduation-cap",
    OUTGOING_SMS_TYPE.WEATHER_KENMET: "cloud-sun-rain",
    OUTGOING_SMS_TYPE.WEATHER_PLANTVILLAGE: "cloud-sun-rain",
    OUTGOING_SMS_TYPE.MARKET_PRICE: "money-bill-trend-up",
    OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION: "user-tie",
    OUTGOING_SMS_TYPE.VOUCHER: "money-bill-1-wave",
    OUTGOING_SMS_TYPE.WEATHER_AND_MARKET: "bolt",
}
