import re

from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from sms import constants as sms_constants


class GSMCharacterSetValidator(RegexValidator):
    """
    A regex validator that ensures that all characters are valid GSM characters (including
    the extended set). It does NOT validate message length.
    """
    message = _("Text contains invalid characters.")
    regex = '^[{}]*$'.format(re.escape(sms_constants.GSM_WHITELIST + sms_constants.GSM_EXTENDED_SET))
    code = 'invalid'
