from django.db import models
from django.utils.translation import gettext_lazy as _


class HEARD_ABOUT_US(models.TextChoices):
    FRIEND = 'fr', 'Friend'
    OTHER = 'ot', 'Other'
    SSU = 'ss', 'Shamba Shape Up'
    WEB = 'is', "Ishamba Web"
    BM = 'bm', "Budget Mkononi Web"
    __empty__ = _("Unknown")


class JOIN_METHODS(models.TextChoices):
    BM_CHATBOT = 'bm-chatbot', _("budgetmkononi chatbot")
    CALL = 'call',  _("call to center")
    DIGIFARM = 'digifarm', _("digifarm")
    IMPORT = 'import', _("bulk import")
    SMS = 'sms', _("sms keyword")
    STAFF = 'staff', _("staff created")
    UNKNOWN = '?', _("unknown")
    USSD = 'ussd', _("ussd session")
    WEB = 'web', _("ishamba.com")
    UNSPECIFIED = '', _("Unspecified")
    __empty__ = _("Unknown")


class STOP_METHODS(models.TextChoices):
    BLACKLIST = 'blacklist', _("MNO blacklist")
    CALL = 'call', _("call to center")
    IMPORT = 'import', _("bulk import")
    INVALID = 'invalid', _("invalid number")
    SMS = 'sms', _("sms keyword")
    STAFF = 'staff', _("staff created")
    UNKNOWN = '?', _("unknown")
    __empty__ = _("Unknown")

