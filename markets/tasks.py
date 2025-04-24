from django.apps import apps
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone
from django.conf import settings

from celery.utils.log import get_task_logger
from django_tenants.utils import schema_context

from core.tasks import BaseTask
from core.utils.clients import get_all_clients
from ishamba.celery import app
from markets.models import MarketPriceMessage
from sms.constants import OUTGOING_SMS_TYPE
from sms.tasks import send_message


logger = get_task_logger(__name__)


@app.task(base=BaseTask)
def send_premium_market_prices():
    """
    Sends market prices to all premium customers that can receive them.
    """
    # Imported here to prevent circular import issues
    from markets.delivery import MarketPriceSender
    for client in get_all_clients():
        with schema_context(client.schema_name):
            # Find customers with 'Premium' subscription
            customer_model = apps.get_model('customers', 'Customer')
            customers = customer_model.objects.premium()
            sender = MarketPriceSender(customers=customers)
            sender.send_messages()


# @app.task(base=BaseTask)
# def send_digifarm_market_prices():
#     """
#     Sends market prices to all digifarm customers
#     """
#     # Imported here to prevent circular import issues
#     from markets.delivery import MarketPriceSender
#     for client in get_all_clients():
#         with schema_context(client):
#             # Find customers with 'Premium' subscription
#             customers = Customer.objects.exclude(digifarm_farmer_id=None)
#             sender = MarketPriceSender(customers=customers)
#             sender.send_messages()


@app.task(base=BaseTask)
def send_freemium_market_prices():
    """
    Sends market prices to all freemium customers that can receive them.
    """
    # Imported here to prevent circular import issues
    from markets.delivery import MarketPriceSender
    from customers.models import Customer
    for client in get_all_clients():
        with schema_context(client.schema_name):
            # Find freemium customers
            customers = Customer.objects.freemium()
            sender = MarketPriceSender(customers=customers)
            sender.send_messages()


@app.task(base=BaseTask, ignore_result=True)
def send_market_price_sms(schema_name: str, mpm: MarketPriceMessage, customer):
    """ Sends a Market Price update in an OutgoingSMS to a given recipient. """
    from sms.models import OutgoingSMS
    with schema_context(schema_name):
        if isinstance(mpm, int):
            mpm = MarketPriceMessage.objects.get(pk=mpm)

        # Copy the relevant details into the message 'extras' dict.
        extra = {
            'marketpricemessage_id': mpm.pk,
        }
        try:
            with transaction.atomic():
                outgoing_sms, __ = OutgoingSMS.objects.get_or_create(
                    text=mpm.text,
                    message_type=OUTGOING_SMS_TYPE.MARKET_PRICE,
                    extra__marketpricemessage_id=mpm.pk,
                    defaults={'time_sent': timezone.now(),
                              'sent_by_id': mpm.creator_id,
                              'extra': extra,
                              })
        except (OutgoingSMS.MultipleObjectsReturned, IntegrityError) as e:
            logger.exception(e)
            outgoing_sms = OutgoingSMS.objects.filter(text=mpm.text,
                                                      message_type=OUTGOING_SMS_TYPE.MARKET_PRICE,
                                                      extra__marketpricemessage_id=mpm.id).first()
        send_message(outgoing_sms.id, [customer.id], sender=settings.SMS_SENDER_MARKET_PRICE)
