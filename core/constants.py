from django.db import models
from django.utils.translation import gettext_lazy as _


JOB_START_HOUR, JOB_START_MIN, JOB_START_SEC = 8, 0, 0
DAILY_JOB_START_HOUR = 14

# The following constants must be of the form which is passable as a keyword
# argument to datetime.relativedelta.relativedelta
DATE_RESOLUTION_DAYS = 'days'
DATE_RESOLUTION_WEEKS = 'weeks'
DATE_RESOLUTION_MONTHS = 'months'
DATE_RESOLUTION_CHOICES = (
    (DATE_RESOLUTION_DAYS, 'Day'),
    (DATE_RESOLUTION_WEEKS, 'Week'),
    (DATE_RESOLUTION_MONTHS, 'Month'),
)


# ACTION_VERBS
CUSTOMER_SENT_SMS = 'sent sms'
CUSTOMER_RECIEVED_SMS = 'received sms'
CUSTOMER_SUBSCRIBED = 'subscribed to'
CUSTOMER_UNSUBSCRIBED = 'unsubscribed from'
ACTIVITY_TIP_SENT = 'received tip'

# ACTION TEMPLATES
ACTION_TEMPLATES = {
    CUSTOMER_SENT_SMS: 'customers/activities/sent_sms.html',
    CUSTOMER_RECIEVED_SMS: 'customers/activities/received_sms.html',
    CUSTOMER_SUBSCRIBED: 'customers/activities/subscribe.html',
    CUSTOMER_UNSUBSCRIBED: 'customers/activities/unsubscribe.html',
    ACTIVITY_TIP_SENT: 'customers/activities/tip_sent.html',
}


class LANGUAGES(models.TextChoices):
    BANTU = 'bnt', _('Bantu')
    BEMBA = 'bem', _('Bemba')  # Zambia
    ENGLISH = 'eng', _('English')
    KISWAHILI = 'swa', _('Kiswahili')  # Tanzania, Kenya, Uganda
    LOZI = 'loz', _('Lozi')  # Zambia
    LUGANDA = 'lug', _('Luganda')  # Uganda
    NYANJA = 'nya', _('Nyanja')  # Zambia. aka Chewa, aka Chichewa in Malawi.
    TONGA = 'toi', _('Tonga')  # Zambia, Zimbabwe
    __empty__ = _('(Unknown)')


class FARM_SIZES(models.TextChoices):
    LESS_THAN_1 = '0.50', _('Less than 1')
    ONE_TO_TWO = '1.50', _('1-2')
    THREE_TO_FIVE = '4.00', _('3-5')
    SIX_TO_TEN = '8.00', _('6-10')
    TEN_TO_TWENTY = '15.00', _('11-20')
    MORE_THAN_TWENTY = '30.00', _('More than 20')
    UNSPECIFIED = '', _("Unspecified")
    __empty__ = _('(Unknown)')


class FARM_SIZES_SPECIFIED(models.TextChoices):
    LESS_THAN_1 = '0.50', _('Less than 1')
    ONE_TO_TWO = '1.50', _('1-2')
    THREE_TO_FIVE = '4.00', _('3-5')
    SIX_TO_TEN = '8.00', _('6-10')
    TEN_TO_TWENTY = '15.00', _('11-20')
    MORE_THAN_TWENTY = '30.00', _('More than 20')


class PHONE_TYPES(models.TextChoices):
    SMARTPHONE = 's', _('Smartphone')
    BASICPHONE = 'b', _('Basic phone')
    FEATUREPHONE = 'f', _('Feature phone')
    UNSPECIFIED = '', _("Unspecified")
    __empty__ = _('(Unknown)')


class SEX(models.TextChoices):
    FEMALE = 'f', _('Female')
    MALE = 'm', _('Male')
    UNSPECIFIED = '', _("Unspecified")
    __empty__ = _('(Unknown)')


class SEX_SPECIFIED(models.TextChoices):
    FEMALE = 'f', _('Female')
    MALE = 'm', _('Male')


class MARITAL_STATUS(models.TextChoices):
    MARRIED = 'm', 'Married'
    SINGLE = 's', 'Single'
    UNSPECIFIED = '', _("Unspecified")
    __empty__ = _('(Unknown)')
