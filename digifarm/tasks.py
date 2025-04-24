import logging
from typing import Iterable

from ishamba.celery import app
from core.constants import LANGUAGES
from customers.models import Customer
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS
from sms.tasks import send_message
from sms.utils import get_i10n_template_text

logger = logging.getLogger(__name__)


@app.task()
def send_digifarm_bulk_sms(digifarm_ids: Iterable[str], template_name: str = None, sms_text: str = None):
    if not (template_name or sms_text):
        raise ValueError("You must provide a template or the message text")
    customers = Customer.objects.filter(digifarm_farmer_id__in=digifarm_ids)
    if template_name:
        swahili_customers = customers.filter(preferred_language=LANGUAGES.KISWAHILI)
        english_customers = Customer.objects.filter(preferred_language=LANGUAGES.ENGLISH)
        swahili_message_text = get_i10n_template_text(template_name, LANGUAGES.KISWAHILI)
        english_message_text = get_i10n_template_text(template_name, LANGUAGES.ENGLISH)
        english_message, created = OutgoingSMS.objects.get_or_create(
            text=english_message_text,
            defaults={'type': OUTGOING_SMS_TYPE.BULK}
        )
        swahili_message, created = OutgoingSMS.objects.get_or_create(
            text=swahili_message_text,
            defaults={'type': OUTGOING_SMS_TYPE.BULK}
        )
        send_message.delay(english_message.id, list(english_customers.values_list('id', flat=True)))
        send_message.delay(swahili_message.id, list(swahili_customers.values_list('id', flat=True)))
    elif sms_text:
        message, created = OutgoingSMS.objects.get_or_create(
            text=sms_text,
            defaults={'type': OUTGOING_SMS_TYPE.BULK}
        )
        send_message.delay(message.id, list(customers.values_list('id', flat=True)))
