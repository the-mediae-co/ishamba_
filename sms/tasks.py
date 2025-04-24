import decimal
import random
import time
from datetime import timedelta
from functools import lru_cache
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

import sentry_sdk
from celery.utils.log import get_task_logger
from django_tenants.utils import (get_tenant_model, schema_context,
                                  tenant_context)
from tenant_schemas_celery.task import TenantTask

from core.tasks import BaseTask
from core.utils.models import queryset_iterator
from customers.constants import STOP_METHODS
from customers.models import Customer
from gateways import AfricasTalkingGateway, DigifarmGateway, gateways
from gateways.exceptions import GatewayRetryException
from ishamba.celery import app
from sms.constants import OUTGOING_SMS_TYPE
from world.models import Border

from .models.metrics import DailyOutgoingSMSSummary
from .models.outgoing import OutgoingSMS, SMSRecipient

logger = get_task_logger(__name__)


def backoff(retries):
    """
    Exponential back-off with an initial 60 second delay. Random jitter added
    to prevent the Thundering Herd Problem.
    """
    return 59 + int(random.uniform(2, 4)) ** retries


def daterange(start_date, end_date):
    """ Produce a sequence of dates (forward or backwards), inclusive of both ends """
    backwards = start_date > end_date
    delta = abs((start_date - end_date).days) + 1  # To make the dates range inclusive
    if backwards:
        seq_range = range(0, -delta, -1)
    else:
        seq_range = range(0, delta, 1)  # dates, inclusive
    for n in seq_range:
        yield start_date + timedelta(n)


class SendMessageBase(TenantTask):
    """ A celery task for sending a message """

    max_retries = 0

    @lru_cache(maxsize=None)
    def get_gateway(self, gateway_id, **kwargs):
        return gateways.get_gateway(gateway_id, **kwargs)

    def on_retry(self, exc, *args, **kwargs):
        """
        Log exception and retry
        """
        logger.warn('Transient message sending error occurred', exc_info=True)
        super(SendMessageBase, self).on_retry(exc, *args, **kwargs)

    def on_failure(self, exc, *args, **kwargs):
        """
        Log exception on failure
        """
        logger.exception(exc)
        super(SendMessageBase, self).on_failure(exc, *args, **kwargs)


# Adding a one-hour tenant cache to reduce DB load
# https://pypi.org/project/tenant-schemas-celery/0.3.0/
@app.task(base=SendMessageBase, bind=True, ignore_result=True, tenant_cache_seconds=3600)
def send_message(self, sms_id: int, recipient_ids: Optional[list[int]] = None, **kwargs):
    """
    Sends a message to the given recipients via all gateways

    Args:
        sms_id (int): OutgoingSMS id to send to the recipients.
        recipient_ids (int): An list of customer ids.
        kwargs: Passed to gateway.send_message as extra sending arguments.

    Raises:
        ValidationError: When either the message or at least one recipient
            is invalid.
    """
    if not recipient_ids:
        return

    recipients = (Customer.objects.filter(id__in=recipient_ids)
                  .exclude(smsrecipient__message_id=sms_id))
    for gateway_id in gateways._gateways:
        gateway = self.get_gateway(gateway_id)
        gateway_recipients = (gateway.filter_queryset(recipients)
                              .values_list('id', flat=True)
                              .distinct())

        for batch in queryset_iterator(gateway_recipients, gateway.RECIPIENT_BATCH_SIZE):
            send_message_via_gateway.delay(sms_id=sms_id, recipient_ids=list(batch), gateway_id=gateway_id, **kwargs)


# Adding a one-hour tenant cache to reduce DB load
# https://pypi.org/project/tenant-schemas-celery/0.3.0/
@app.task(base=SendMessageBase, bind=True, ignore_result=True, tenant_cache_seconds=3600)
def send_message_via_gateway(self, sms_id: int, recipient_ids, gateway_id: int, gateway_kwargs={}, **kwargs):
    """
    Sends a message to the given recipients via the specified Gateway
    (defaults to gateways.AT).

    Args:
        sms_id (int): Primary key of OUtgoingSMS to send.
        recipient_ids (iterable[int]): An iterable of recipient Customer object primary keys.
        text (str): A message string to send to the recipients.
        sender: The sender identifier (e.g. short code, alphanumeric etc.)
        gateway_id: The gateway to send from (defaults to gateways.AT).
        kwargs: Passed to gateway.send_message as extra sending arguments.
        gateway_kwargs: kwargs to use when getting the appropriate gateway

    Raises:
        ValidationError: When either the message or at least one recipient
            is invalid.
    """
    gateway = self.get_gateway(gateway_id, **gateway_kwargs)
    message = OutgoingSMS.objects.get(id=sms_id)
    try:
        gateway.send_message(message=message, recipient_ids=recipient_ids, **kwargs)
    except GatewayRetryException as e:
        logger.warning(
            f"Gateway retry exception for {message.id} to {recipient_ids}, {e}"
        )


@app.task(base=BaseTask, ignore_result=True)
def record_delivery_report_task(schema_name, mno_message_id, status='', failure_reason=''):
    with schema_context(schema_name):
        try:
            sms_recipient = SMSRecipient.objects.get(gateway_msg_id=mno_message_id)
        except SMSRecipient.DoesNotExist:
            logger.warning("Delivery report for unknown message: %s", mno_message_id,
                           extra={'status': status, 'failure_reason': failure_reason})
            return
        except SMSRecipient.MultipleObjectsReturned:
            logger.error("Duplicate mno_message_id's detected: %s", mno_message_id)
            # Continue updating message status with the first one returned
            sms_recipient = SMSRecipient.objects.filter(gateway_msg_id=mno_message_id).first()

        if sms_recipient is None:
            logger.error("Could not find SMSRecipient corresponding to gateway message id: {gateway_msg_id}")
            return


        # Update the message status
        sms_recipient.delivery_status = status
        sms_recipient.failure_reason = failure_reason
        sms_recipient.gateway_name = AfricasTalkingGateway.Meta.verbose_name
        sms_recipient.save(update_fields=['delivery_status', 'failure_reason', 'gateway_name'])

        # If the failure status is 'UserInBlackList', it means that the customer has
        # requested AT to stop delivering messages from iShamba.
        # TODO: Handle other failure modes more intelligently
        if failure_reason == 'UserInBlackList':
            try:
                # Set the has_requested_stop flag in our DB so we stop sending messages
                customer = Customer.objects.get(pk=sms_recipient.recipient.id)
                if not customer.has_requested_stop:
                    customer.has_requested_stop = True
                    customer.stop_method = STOP_METHODS.BLACKLIST
                    customer.stop_date = timezone.now().date()
                    customer.save(update_fields=['has_requested_stop', 'stop_method', 'stop_date'])
                    logger.warning(f"AT added customer to stopped list: {sms_recipient.recipient.id}"
                                   f" after message: {mno_message_id}")
            except Customer.DoesNotExist:
                logger.error("Could not find customer corresponding to delivery notification: {recipient_id}")
        # UnsupportedNumberType is typically a non-mobile phone (cannot receive sms messages)
        elif failure_reason == 'UnsupportedNumberType':
            try:
                # Set the has_requested_stop flag in our DB so we stop sending messages
                customer = Customer.objects.get(pk=sms_recipient.recipient.id)
                if not customer.has_requested_stop:
                    customer.has_requested_stop = True
                    customer.stop_method = STOP_METHODS.INVALID
                    customer.stop_date = timezone.now().date()
                    customer.save(update_fields=['has_requested_stop', 'stop_method', 'stop_date'])
                    logger.warning(f"AT added customer to stopped list: {sms_recipient.recipient.id}"
                                   f" after message: {mno_message_id}")
            except Customer.DoesNotExist:
                logger.error("Could not find customer corresponding to delivery notification: {recipient_id}")


@app.task(base=BaseTask, ignore_result=False)
def update_dailyoutgoingsmssummary(start_date=None):
    """
    update_dailyoutgoingsmssummaries() calls this method for each schema separately.
    """
    schema_name = connection.schema_name

    at_gateway_name = AfricasTalkingGateway.Meta.verbose_name
    df_gateway_name = DigifarmGateway.Meta.verbose_name
    gateways = [at_gateway_name, df_gateway_name]

    # Re-count the last 5 days of OutgoingSMS records. This helps allow
    # message delivery status to take time and cross over a day boundary,
    # plus recovery in case of failure or task cancellation on any day.
    end_date = timezone.now().date()
    if not start_date:
        start_date = end_date - timedelta(days=5)
    countries = Border.objects.filter(level=0)

    created_count = 0
    updated_count = 0

    tic = time.perf_counter()
    # We create distinct objects for each country/day/gateway_name/message_type combination
    for country in countries:
        for day in daterange(end_date, start_date):  # backwards, inclusive of both ends
            prev_summary = DailyOutgoingSMSSummary.objects.filter(date=day, country_id=country.id).first()

            logger.debug(f"*** Summarizing {schema_name} {country.name} {day}")

            for type_obj in OUTGOING_SMS_TYPE:
                msg_type = type_obj.value
                if msg_type == '?':
                    continue
                t1 = time.perf_counter()
                message_ids = list(OutgoingSMS.objects.filter(created__date=day,
                                                              message_type=msg_type) \
                                   .values_list('id', flat=True))
                if not message_ids:
                    logger.debug(f"Skipping {msg_type}: no records")
                    continue
                message_ids.sort()

                gateway_names = list(SMSRecipient.objects.filter(message_id__in=message_ids)
                                     .order_by('gateway_name')
                                     .distinct('gateway_name')
                                     .values_list('gateway_name', flat=True))

                for gateway_name in gateway_names:
                    t2 = time.perf_counter()
                    costs = (SMSRecipient.objects.filter(message_id__in=message_ids,
                                                         gateway_name=gateway_name,
                                                         recipient__border0=country)
                             .values_list('cost', flat=True))
                    count = costs.count()
                    t3 = time.perf_counter()
                    # Hard code to be country currency for now.
                    if country.name == 'Kenya':
                        cost_units = 'kes'
                    elif country.name == 'Uganda':
                        cost_units = 'ugx'
                    else:
                        cost_units = '?'
                    total_cost = sum(map(decimal.Decimal, costs))
                    t4 = time.perf_counter()

                    obj, created = DailyOutgoingSMSSummary.objects.update_or_create(
                        date=day,
                        country_id=country.pk,
                        message_type=msg_type,
                        gateway_name=gateway_name,
                        defaults={
                            'count': count,
                            'cost': total_cost,
                            'cost_units': cost_units,
                            'extra': {'message_ids': message_ids}
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                    t5 = time.perf_counter()
                    logger.debug(f"{msg_type}: t2-t1={t2 - t1:0.1f}, t3-t2={t3 - t2:0.1f}, "
                                 f"t4-t3={t4 - t3:0.1f}, t5-t4={t5 - t4:0.1f}")

    toc = time.perf_counter()
    logger.debug(f"Created {created_count} and updated {updated_count} DailyOutgoingSMSSummary "
                 f"objects in {tic - toc:0.1f} seconds")
    return True


@app.task(base=BaseTask, ignore_result=True)
def update_dailyoutgoingsmssummaries():
    """
    Celery.beat calls this task. Since tasks cannot be called per tenant schema,
    this method calls update_dailyoutgoingsmssummary() or each schema separately.
    """
    for tenant in get_tenant_model().objects.exclude(schema_name='public'):
        with tenant_context(tenant):
            update_dailyoutgoingsmssummary.delay()


@app.task(base=SendMessageBase, bind=True, ignore_result=True)
def send_nps_queries(self, schema_name: str = 'ishamba', num_recipients: int = 100):
    # Track performance
    t0 = time.perf_counter()

    msgs = {
        'eng': "Based on the service you received, how likely are you to recommend iShamba to friends "
               "or family? On a scale of 0 to 10, with 0 being lowest and 10 the highest.",
        'swa': "Kwa mizani ya 0 hadi 10, 0 ikiwa ya chini zaidi na 10 ya juu zaidi, kuna uwezekano "
               "gani wewe kuipendekeza huduma ya iShamba kwa marafiki au familia?"
    }

    # How recent we consider the most recent query response to still be active
    earliest_date = timezone.localtime(timezone.now()) - timedelta(days=360)
    response_window = timezone.localtime(timezone.now()) - timedelta(days=5)

    kenya = Border.objects.get(country='Kenya', level=0)

    tenant_schema_name = 'fast_test' if hasattr(settings, 'TEST') and settings.TEST else 'ishamba'
    with schema_context(tenant_schema_name):
        # Find customers in Kenya who have not been asked the NPS question nor DATA QUERY recently
        sent_msg_ids = set(OutgoingSMS.objects.filter(
            message_type=OUTGOING_SMS_TYPE.NPS_REQUEST,
            time_sent__gte=earliest_date,
        ).values_list('id', flat=True))
        t1 = time.perf_counter()

        sent_msg_ids = sent_msg_ids.union(set(OutgoingSMS.objects.filter(
            message_type=OUTGOING_SMS_TYPE.DATA_REQUEST,
            time_sent__gte=response_window,
        ).values_list('id', flat=True)))
        t2 = time.perf_counter()

        recipient_ids = Customer.objects.filter(
            has_requested_stop=False,
            border0=kenya,
            preferred_language__in=('eng', 'swa'),
            # phones__number__startswith='+254',
        ).exclude(  # Exclude customers who recently received an NPS_REQUEST request
            smsrecipient__message_id__in=sent_msg_ids
        ).order_by('?').values_list('id', flat=True)[:num_recipients]
        t3 = time.perf_counter()

        total_count = 0

        for lang in ('eng', 'swa'):
            recipients = Customer.objects.filter(pk__in=recipient_ids, preferred_language=lang)
            recipient_count = recipients.count()
            if recipient_count > 0:
                try:
                    sms = OutgoingSMS.objects.create(text=msgs[lang],
                                                     message_type=OUTGOING_SMS_TYPE.NPS_REQUEST)
                    send_message.delay(sms_id=sms.id, recipient_ids=list(recipients.values_list('id', flat=True)), sender='21606', exclude_stopped_customers=False)
                    total_count += recipient_count
                except ValidationError:  # e.g. invalid phone numbers
                    phones = recipients.values_list('phones__number', flat=True)
                    sentry_sdk.capture_message("ValidationError: ", ','.join(phones))
                    # The message was not sent so delete the OutgoingSMS and throw
                    # these customers back into the random NPS pool for next time
                    if sms:
                        sms.delete()
            else:
                sentry_sdk.capture_message("WARNING: No customers found for NPS message")

    t4 = time.perf_counter()
    logger.debug(f"NPS query performance: t1={t1 - t0:0.1f}, t2={t2 - t1:0.1f}, t3={t3 - t2:0.1f}, t4={t4 - t3:0.1f}, total={t4 - t3:0.1f}")
    if t4 - t0 > 300:
        sentry_sdk.capture_message(f"Slow NPS query sent to {total_count} customers in {t4 - t0:0.1f} secs, "
                                   f"{total_count / (t4 - t0):0.1f}/s")
