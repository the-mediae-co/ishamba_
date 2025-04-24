from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


CALENDAR_TYPE_SEASONAL = 'seasonal'
CALENDAR_TYPE_EVENT_BASED = 'event-based'


GRADUATION_MSG = ("Your {old} tips have come to an end, and you will receive "
                  "general {new} tips from now on.")


class COMMODITY_TYPES(TextChoices):
    CROP = ('crop', _('Crop'))
    LIVESTOCK = ('livestock', _('Livestock'))

class SUBSCRIPTION_FLAG(TextChoices):
    PREMIUM = ('premium', _('Premium'))
    FREEMIUM = ('freemium', _('Freemium'))
    __empty__ = _('No subscription flags')
