from __future__ import annotations

import contextlib
import decimal
from logging import getLogger
from typing import TYPE_CHECKING, Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import ProgrammingError, transaction
from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout

from customers.constants import STOP_METHODS
from gateways import SMSGateway
from sms.constants import KENYA_COUNTRY_CODE, UGANDA_COUNTRY_CODE, ZAMBIA_COUNTRY_CODE
from sms.signals.signals import sms_sent

if TYPE_CHECKING:
    from sms.models import OutgoingSMS

from .exceptions import (AfricasTalkingGatewayException,
                         AfricasTalkingGatewayRetryException)

logger = getLogger(__name__)


class AfricasTalkingGateway(SMSGateway):
    MESSAGE_ENQUEUE_AT = 100

    class Meta:
        gateway_id = 0
        short_name = 'AT'
        verbose_name = 'AfricasTalking'

    def __init__(self, *args, **kwargs):
        self.gateway_kwargs = kwargs.copy()

        alias = kwargs.pop('alias', 'default')
        gateway_secrets = self._get_secrets(alias=alias)

        super(AfricasTalkingGateway, self).__init__(*args, **kwargs)

        # store args
        self.username = gateway_secrets.get('username')
        self.api_key = gateway_secrets.get('api_key')
        self.default_sender = gateway_secrets.get('sender')

        if not all((self.username, self.api_key)):
            raise ImproperlyConfigured(
                "Missing AfricasTalkingGateway configuration. Check your "
                "GATEWAY_SECRETS setting.")

        # initialise requests.Session with the required headers
        self.session = requests.Session()
        self.session.headers.update(
            {'Accept': 'application/json',
             'apikey': self.api_key})

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        from world.models import Border
        return queryset.filter(
            ~Q(border0=Border.objects.get(name="Zambia", level=0)),
            phones__isnull=False,
            digifarm_farmer_id__isnull=True,
        )

    def generate_customer_map(self, results):
        from customers.models import CustomerPhone
        numbers = [r['number'] for r in results]
        customers = CustomerPhone.objects.filter(number__in=numbers).values_list('customer_id', 'number')
        return {phone: cid for cid, phone in customers}

    def parse_result(self, result):
        number = result['number']
        status = result['status']
        msg_id = result['messageId']
        cost = result['cost']

        return number, status, msg_id, cost

    def _send_message(self, message: OutgoingSMS, phone_numbers: list[str], **kwargs):
        """
        Synchronously sends an SMS from a given sender (short code or
        alphanumeric) to a either a single recipient or list of recipients.

        NOTE: Callers are responsible for validation of both the message and
        the recipients.

        Returns:
            [dict, ...]. List of responses per recipient. e.g.
                {"number"    : "+254711XXXYYY",
                 "cost"      : "KES YY",
                 "status"    : "Success",
                 "messageId" : "ATSid_1"}
        Raises:
            AfricasTalkingGatewayException: Upon failure to send SMS.
            AfricasTalkingGatewayRetryException: Upon transient failure to send
                SMS (thus sending can be retried).
        """
        from customers.models import Customer
        from sms.models import SMSRecipient

        # If we've got a string then it may either be a single number or
        # multiple comma delimited numbers
        break_on = kwargs.pop('break_on', '\n')
        paginate = kwargs.pop('paginate', True)
        sender: str = kwargs.pop('sender', None)

        num_recipients = len(phone_numbers)

        # Enqueue (i.e. don't wait for ack from telco) if we have more
        # recipients than the threshold
        if num_recipients >= self.MESSAGE_ENQUEUE_AT:
            kwargs.setdefault('enqueue', 1)

        text = message.text

        text_pages = self.split_text_into_pages(text, break_on=break_on, paginate=paginate)

        len_pages = len(text_pages)
        if len_pages > self.MAX_SMS_PER_MESSAGE:
            raise ValidationError(
                self.error_messages['message_requires_too_many_sms'],
                params={'max_sms_per_message': self.MAX_SMS_PER_MESSAGE})

        for page_idx, page_text in enumerate(text_pages, start=1):
            # build the POST data to send to API.
            data = {
                'username': self.username,
                'to': ','.join(phone_numbers),
                'message': page_text,
                'enqueue': kwargs.get('enqueue', 1),

                # defaults that we don't currently care about
                # 'keyword': None,
                # 'bulkSMSMode': 1,
                # 'keyword': None,
                # 'linkId': None,
            }
            # Allow AFRICASTALKING as sender if None
            if sender:
                data['from'] = sender
            data.update(**kwargs)

            logger.debug(
                'Attempting to send outgoing SMS "%(text)s" to %(recipients)s',
                {'text': text, 'recipients': phone_numbers},
                extra={'post_data': data})

            try:
                # try submitting request to AT
                resp = self.session.post(settings.AT_SMS_ENDPOINT,
                                        data=data,
                                        timeout=self.TIMEOUT)

                # if we get a 4XX or 5XX status code, raise exception
                resp.raise_for_status()
            except (Timeout, ConnectionError, HTTPError) as e:
                # Unless AT returns 200 OK then the message(s) hasn't been sent.
                # Thus, it is safe to retry so we raise specific error.
                # Source: AT representative via help-desk chat.
                logger.warning('Failed to send SMS "%(text)s" to %(recipients)s',
                            {'text': text, 'recipients': phone_numbers},
                            extra={'post_data': data},
                            exc_info=True)
                raise AfricasTalkingGatewayRetryException(e)

            try:
                # if we have a response try and decode it and return the relevant
                # portion
                response_data = resp.json()

                logger.debug('Outgoing SMS sent',
                            extra={'response': response_data})

            except (ValueError, IndexError):
                raise AfricasTalkingGatewayException(
                    'Response could not be decoded: {}'.format(resp.text))
            else:
                results = response_data['SMSMessageData']['Recipients']
                customer_map = self.generate_customer_map(results)
                receipts_to_create = []
                recipient_pks = []
                stopped_customer_ids = []
                for result in results:
                    try:
                        number, status, msg_id, cost_details = self.parse_result(result)
                    except KeyError:
                        logger.error('Invalid message delivery result received from gateway.',
                                    exc_info=True,
                                    extra={'result': result})
                        continue

                    customer_id = customer_map.get(number)

                    # If we tried to send an sms to a non-mobile number, we should mark the
                    # customer as having requested stop so we don't keep sending messages to them.
                    if status == "UnsupportedNumberType":
                        if customer_id:
                            stopped_customer_ids.append(customer_id)
                        continue

                    if status != 'Success':
                        logger.error(
                            "Failed to send %(sms)s to %(number)s. Status: %(status)s.",
                            {'sms': message, 'number': number, 'status': status},
                            extra={'result': result})
                        continue

                    if customer_id:
                        cost_units, cost = cost_details.split(' ')
                        cost_units = cost_units.lower() if cost_units else '?'
                        if cost:
                            cost = decimal.Decimal(cost)
                        else:
                            cost = decimal.Decimal('0.00')
                        receipts_to_create.append(
                            SMSRecipient(
                                recipient_id=customer_id,
                                message=message,
                                gateway_name=AfricasTalkingGateway.Meta.verbose_name,
                                page_index=page_idx,
                                gateway_msg_id=msg_id,
                                cost=cost,
                                cost_units=cost_units,
                                extra={
                                    'messageId': msg_id,  # Retained to keep data consistent
                                    'number': number,
                                    'page': {
                                        'total': len_pages,
                                    }
                                }
                            )
                        )
                        recipient_pks.append(customer_id)

                if receipts_to_create:
                    recipient_records = SMSRecipient.objects.bulk_create(receipts_to_create)
                    transaction.on_commit(lambda: SMSRecipient.index_many(recipient_records))

                    # record django-activity-stream activity
                    sms_sent.send_robust(sender=message.__class__, sms=message,
                                         recipient_ids=recipient_pks)



                if stopped_customer_ids:
                    # Set has_requested_stop=True for these customers
                    # so that we don't attempt to send more messages.
                    customers = Customer.objects.filter(pk__in=stopped_customer_ids)
                    update_count = customers.update(has_requested_stop=True,
                                                    stop_method=STOP_METHODS.INVALID,
                                                    stop_date=timezone.now().date())

                    if update_count != customers.count():
                        logger.error(f"Attempted to update {customers.count()} customers but "
                                    f"only succeeded in updating {update_count}")

                    stopped_ids_strs = [str(x) for x in stopped_customer_ids]
                    if stopped_ids_strs:
                        logger.warning(
                            f"Failed to send sms {message.text} due to UnsupportedNumberType. "
                            f"Setting has_requested_stop=True for AT customer pks: {','.join(stopped_ids_strs)}"
                        )

    def send_message(self, message: OutgoingSMS, recipient_ids: Union[QuerySet, list[int]], **kwargs):
        """
        Sends a message to the given recipients via the sms.tasks.send_message
        celery task.

        Args:
            message (OutgoingSMS): The message being sent
            recipient_ids (iterable): An iterable of recipient ids.
            kwargs: Passed to self._send_message as extra sending arguments.

        Raises:
            ValidationError: When either the message or at least one recipient
                is invalid.
        """
        # NOTE: imported here to prevent circular import
        from customers.models import Customer, CustomerPhone

        phones_query = CustomerPhone.objects.filter(customer=OuterRef('pk'), is_main=True)
        recipients = (Customer.objects
                      .filter(id__in=recipient_ids, phones__isnull=False)
                      .annotate(phone_number=Subquery(phones_query.values('number')[:1])))

        # If we were provided a 'using_numbers' kwarg, use these numbers for their
        # corresponding customer recipients, instead of their main_phone number
        using_numbers = kwargs.pop('using_numbers', [])
        if using_numbers:
            if not isinstance(using_numbers, list):
                raise ProgrammingError(f'The using_numbers kwarg must be a list')
            numbered_customer_ids = CustomerPhone.objects.filter(number__in=using_numbers).values_list('customer_id', flat=True)
            recipients = recipients.exclude(id__in=numbered_customer_ids)

        # filter out customers with phone numbers but none marked main (FIXME(apryde): idk. if this is a valid state in prod but exists in tests)
        phone_numbers = [number for number in recipients.values_list('phone_number', flat=True).distinct() if number is not None]

        # Remove duplicates and add the specified numbers back in
        phone_numbers = set(phone_numbers)
        phone_numbers.update(using_numbers)


        self._send_message(message=message, phone_numbers=phone_numbers, **kwargs)

    def send_message_to_phones(self, message: OutgoingSMS, phone_ids: QuerySet, **kwargs):
        from customers.models import CustomerPhone
        allow_international = kwargs.pop('allow_international', False)
        country_prefix = kwargs.pop('country_prefix', None)

        if allow_international:
            # Skip country code or sender checks.
            recipient_numbers = (
                CustomerPhone.objects.filter(id__in=phone_ids)
                                    .exclude(number__startswith='+245')  # exclude the fake 245 duplicate customers
                                    .values_list('number', flat=True)
            )
        elif country_prefix:
            # Search only for the country_code preamble if supplied
            recipient_numbers = (
                CustomerPhone.objects.filter(id__in=phone_ids,
                                            number__startswith=country_prefix)
                                    .values_list('number', flat=True)
            )
        else:
            # Not supplied a country_code but not allowing international, so accept only
            # country codes of all countries that we operate in.
            recipient_numbers = (
                CustomerPhone.objects.filter(id__in=phone_ids).filter(
                    Q(number__startswith=f'+{KENYA_COUNTRY_CODE}') |
                    Q(number__startswith=f'+{UGANDA_COUNTRY_CODE}') |
                    Q(number__startswith=f'+{ZAMBIA_COUNTRY_CODE}')
                ).values_list('number', flat=True)
            )

        if len(recipient_numbers) == 0:
            logger.warning(
                'Attempted to send %s id:%d to 0 unique recipients (provided: '
                '%d customers)', self.__class__, message.pk, recipient_numbers.count())
            return None

        self._send_message(message=message, phone_numbers=list(recipient_numbers), **kwargs)


    def call(self, from_, to_):
        """
        Handles dialling calls from an AT registered phone number to a
        given phone number you wish to dial.

        Raises:
            AfricasTalkingGatewayException: When call cannot be placed.
        """
        data = {
            'username': self.username,
            'from': from_,
            'to': to_
        }

        try:
            # try submitting request to AT
            resp = self.session.post(settings.AT_VOICE_ENDPOINT,
                                     data=data,
                                     timeout=self.TIMEOUT)

            # if we get a 4XX or 5XX status code, raise exception
            resp.raise_for_status()
        except (Timeout, ConnectionError) as e:
            logger.warning('Failed to send place call: {}'.format(e))
            raise AfricasTalkingGatewayException(e)
        except HTTPError:
            try:
                error_msg = resp.json()['ErrorMessage']
                raise AfricasTalkingGatewayException(error_msg)
            except (ValueError, IndexError):
                raise AfricasTalkingGatewayException(
                    'Response could not be decoded: {}'.format(resp.text))

    @staticmethod
    @contextlib.contextmanager
    def mock_success_response():
        """
        contextmanager to support disabling sending when settings.DEBUG = True.
        """
        import responses  # dev-only requirement

        from .testing import _success_response_callback  # circular import

        logger.debug("Mocking successful message send.")
        with responses.RequestsMock() as resps:
            resps.add_callback(
                responses.POST, settings.AT_SMS_ENDPOINT,
                callback=_success_response_callback,
                content_type='application/json')
            yield


class AfricasTalkingGatewayZambia(AfricasTalkingGateway):
    """
    We use an independent AT account for iMunda (Zambia). This class
    facilitates that.
    """

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        from world.models import Border
        return queryset.filter(
            Q(border0=Border.objects.get(name="Zambia", level=0)),
            phones__isnull=False,
            digifarm_farmer_id__isnull=True,
        )

    class Meta:
        gateway_id = 2
        short_name = 'ATZMB'
        verbose_name = 'AfricasTalkingZambia'
