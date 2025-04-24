import logging
import decimal
from typing import Iterable, List, Tuple
from enum import Enum

import sentry_sdk
from sentry_sdk import capture_message

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models, ProgrammingError
from django.db.models import Q
from django.db.models.query import QuerySet
from django.template.defaultfilters import pluralize
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from gateways import gateways

from core.models import TimestampedBase
from customers.models import Customer, CustomerPhone
from search.constants import ENGLISH_ANALYZER
from search.indexes import ESIndexableMixin
from search.fields import ESAnalyzedTextField

from sms.constants import KENYA_COUNTRY_CODE, OUTGOING_SMS_TYPE, UGANDA_COUNTRY_CODE, MAX_SMS_PER_MESSAGE

__all__ = ['OutgoingSMS', 'SMSRecipient']


logger = logging.getLogger(__name__)


class OutgoingSMS(ESIndexableMixin, TimestampedBase):
    """
    A common class to encapsulate all outgoing SMS messages. In earlier stages
    of the platform implementation, there were multiple outgoing message types.
    In August of 2021 these were consolidated into a common class/table.
    """
    INDEX_FIELDS = ['id', 'text', 'sent_by', 'time_sent', 'message_type', 'incoming_sms', 'created']

    text = ESAnalyzedTextField(null=True, analyzer=ENGLISH_ANALYZER)
    time_sent = models.DateTimeField(null=True)

    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                blank=True,
                                null=True,
                                on_delete=models.SET_NULL)

    # This field is used to differentiate outgoing sms types.
    message_type = models.CharField(max_length=8,
                                    choices=OUTGOING_SMS_TYPE.choices,
                                    default=OUTGOING_SMS_TYPE.UNKNOWN)

    # A commonly used reference, so worth declaring as a separate field (with null being legal)
    incoming_sms = models.ForeignKey('sms.IncomingSMS',  # originally from AutomaticResponseSentSMS
                                     blank=True,
                                     null=True,
                                     on_delete=models.PROTECT,  # or SET_NULL. Was originally CASCADE
                                     default=None)

    extra = models.JSONField(blank=True, default=dict)  # a json field to hold any additional data

    # Note: The SMSRecipient object declares a ForeignKey with
    # related_name="recipients", so this message's recipients
    # can be reference via self.recipients.all()

    class Meta:
        verbose_name = "Outgoing SMS"
        indexes = [
            models.Index(fields=['text'], name='outgoingsms_text_idx')
        ]

    def _to_qs(self, customers) -> 'QuerySet[Customer]':
        """
        Best effort to turn whatever was passed to us into a Customer QuerySet
        """
        if isinstance(customers, QuerySet) and customers.model is Customer:
            return customers
        elif isinstance(customers, QuerySet):
            raise ProgrammingError(f'Received unexpected QuerySet of {customers.model}')
        elif isinstance(customers, Customer):
            return Customer.objects.filter(pk=customers.id)
        elif not isinstance(customers, Iterable) or isinstance(customers, str):
            raise ProgrammingError(f"Queryset or List of Customer records expected, got {customers}")

        customers = list(customers)
        if isinstance(customers[0], Customer):
            return Customer.objects.filter(pk__in=[c.id for c in customers])
        if isinstance(customers[0], str):
            # raise ProgrammingError(f"Queryset or List of Customer records expected, got {customers}")
            capture_message("Passing phone numbers for customers!!!")
            logger.warning('Passing phone numbers for customers!!!')
            return Customer.objects.filter_by_phones(customers)

        raise ProgrammingError(f'Received unexpected Iterable of {type(customers[0])}')

    def _update_recorded_senders(self, new_sender: str) -> None:
        from ..utils import get_country_for_sender

        if not new_sender:
            return

        country = get_country_for_sender(new_sender)
        if not country:
            return
        new_country_name = country.name
        update_needed = False

        if 'senders' in self.extra:
            countries = self.extra.get('senders')
            if new_country_name in countries:
                senders_list = countries.get(new_country_name)
                if new_sender not in [str(x) for x in senders_list]:  # cast to strings
                    # we found the country, but not the sender, so append the new one
                    senders_list.append(new_sender)
                    update_needed = True
            else:
                countries[new_country_name] = [new_sender]
                update_needed = True
        else:
            self.extra['senders'] = {
                new_country_name: [new_sender],
            }
            update_needed = True

        if update_needed:
            self.save(update_fields=['extra'])

    def send(self, schema_name: str, customers: QuerySet, sender: str = None,
             exclude_stopped_customers=True, **kwargs):
        """
        Sends the OutgoingSMS message to the given customers.
        This function will _only_ send to Customer objects.
        Raises:
            ValidationError: When the message or recipient(s) are invalid.
        """
        # FIXME(apryde): As far as I'm aware this method is no longer called
        # anywhere in the codebase.
        if settings.MUTE_SMS:
            return

        customers = self._to_qs(customers)

        country_prefix = kwargs.get('country_prefix')
        allow_international = kwargs.get('allow_international', False)
        if not allow_international:
            allowed_country_codes = kwargs.get('allowed_country_codes', [])
            allowed_country_codes.extend([KENYA_COUNTRY_CODE, UGANDA_COUNTRY_CODE])
            kwargs.update({'allowed_country_codes': allowed_country_codes})
            if country_prefix and int(country_prefix) not in allowed_country_codes:
                msg = f"OutgoingSMS.send() improperly configured: "\
                                           f"country_prefix={country_prefix}, "\
                                           f"allowed_country_codes={allowed_country_codes}"
                sentry_sdk.capture_message(msg)
                raise ImproperlyConfigured(msg)

        max_sms_per_message = kwargs.pop('max_allowed_sms_per_message',
                                         MAX_SMS_PER_MESSAGE)

        # Remove stopped customers and those who already received this sms.
        recipients, duplicate_ids = self._get_unique_recipients(customers,
                                                                exclude_stopped_customers,
                                                                **kwargs)

        if not recipients:
            return

        if len(duplicate_ids) > 0:
            logger.debug(
                'Attempted to send %s id:%d to %d duplicate recipient%s',
                self.__class__, self.pk, len(duplicate_ids), pluralize(len(duplicate_ids)))

        if sender:
            self._update_recorded_senders(sender)

        at_gateway = gateways.get_gateway(gateways.AT, alias=schema_name)
        # Number validation can be slow and cause AWS gateway timeouts. Numbers pulled from the
        # DB are assumed to be correct. If not, the SMS gateway e.g. AfricasTalking will reject
        # the number anyway, so there's very little risk for sending without full validation.
        at_gateway.send_message(self, recipients, sender=sender,
                                max_sms_per_message=max_sms_per_message,
                                numbers_need_validation=False, **kwargs)

        # Finally, make sure the time_sent field is set. The message may actually
        # be delayed before sending, but the SMSRecipient objects will catch that.
        # Here, we capture the time that the user issued the command to send the message.
        self.time_sent = now()
        self.save(update_fields=['time_sent'])

    def _get_unique_recipients(
        self,
        customers: 'QuerySet[Customer]',
        exclude_stopped_customers=False, **kwargs
    ) -> Tuple['QuerySet[Customer]', List[int]]:
        """
        From the given customers, returns those customers that have not been
        sent this OutgoingSMS previously.
        """

        # If the caller has not already excluded has_requested_stop customers, do it here.
        if exclude_stopped_customers:
            customers = customers.exclude(has_requested_stop=True)

        customer_ids = customers.values_list('pk', flat=True)

        duplicate_ids = (
            self.get_extant_recipients()
                .filter(recipient_id__in=customer_ids)
                .values_list('recipient__id', flat=True)
        )
        customers = customers.exclude(pk__in=duplicate_ids)

        return customers, duplicate_ids

    def get_extant_recipients(self):
        """
        Returns SMSRecipient QuerySet containing all the prior recipients of
        this message.
        """
        if not self.pk:
            return SMSRecipient.objects.none()

        # page_index=1 just returns the first page of multi-page messages
        return SMSRecipient.objects.filter(message_id=self.pk,
                                           page_index=1)

    def should_index(self)-> bool:
        return True


class SMSRecipient(TimestampedBase, ESIndexableMixin):
    """
    Records the sending of an `sms` to a `Customer`.
     - Note: moving forward this will record the sending of an outgoing SMS to multiple Customers.

    Statuses:
        Pending: Waiting for delivery report from AT
        Sent: The message has successfully been sent by our network.
        Submitted: Submitted to the MSP
        Buffered: Queued by the MSP
        Rejected: Rejected by the MSP (Final status)
        Success: Successfully delivered (Final status)
        Failed: Failed to deliver (Final status)

    Failure reasons:
        InsufficientCredit: Subscriber has run out of credit for premium messages
        InvalidLinkId: Message is sent with an invalid linkId for an onDemand service
        UserIsInactive: Subscriber is inactive or the account deactivated by the MSP
        UserInBlackList: Subscriber is blacklisted for your service
        UserAccountSuspended: Subscriber has been suspended by the MSP
        NotNetworkSubscriber: Message is passed to an MSP where the subscriber doesn't belong
        UserNotSubscribedToProduct: Subscription product which the subscriber has not subscribed to
        UserDoesNotExist: Message is sent to a non-existent mobile number
        DeliveryFailure: Unknown reason (include MSP not reporting reason)
    """
    INDEX_FIELDS = [
        'gateway_name', 'message', 'recipient', 'gateway_msg_id',
        'delivery_status', 'failure_reason', 'cost', 'cost_units',
        'page_index', 'created', 'id'
    ]
    PENDING_STATUSES = ['Pending', 'Sent', 'Submitted', 'Buffered']
    FAILED_STATUSES = ['Rejected', 'Failed']
    SUCCEEDED_STATUSES = ['Success']

    recipient = models.ForeignKey('customers.Customer', on_delete=models.CASCADE)
    message = models.ForeignKey('sms.OutgoingSMS',
                                on_delete=models.CASCADE,
                                related_name="recipients",
                                default=None)

    # The carrier / MNO / gateway that these messages were sent via
    gateway_name = models.CharField(max_length=120, blank=False, null=False, default='?')

    gateway_msg_id = models.CharField(
        blank=True,
        max_length=50,
        null=True,  # Required because of unique constraint with blank=True
        unique=True
    )
    delivery_status = models.CharField(
        default='Pending',
        db_index=True,
        max_length=50,
    )
    failure_reason = models.CharField(
        blank=True,
        db_index=True,
        max_length=50,
    )

    # The gateway reported cost of sending this page / message. Max = 9999.99 units
    cost = models.DecimalField(max_digits=6, decimal_places=2, blank=False, null=False, default=decimal.Decimal(0.00))
    # The units that the total cost is expressed in (e.g. ksh, usd, etc.) lower case
    cost_units = models.CharField(max_length=8, blank=False, null=False, default='?')
    # Which page of the segmented sms this sms recipient record is recording
    page_index = models.PositiveSmallIntegerField(default=1)  # enables up to 32767 pages, which should be sufficient
    # Capture any other details as a JSON dict
    extra = models.JSONField(blank=True, default=dict)

    def should_index(self)-> bool:
        return True

    class Meta:
        verbose_name = "SMS recipient"
        constraints = [
            models.UniqueConstraint(fields=['recipient', 'message', 'page_index'], name='unique_message_recipient'),
        ]
