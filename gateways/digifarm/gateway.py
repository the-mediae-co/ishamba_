from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Any, Union

from django.conf import settings
from django.core.cache import cache
from django.db.models import QuerySet

if TYPE_CHECKING:
    from sms.models import OutgoingSMS

import requests

from gateways import SMSGateway

logger = getLogger(__name__)


class DigifarmGateway(SMSGateway):
    MESSAGE_ENQUEUE_AT = 100
    SMS_ENDPOINT = settings.DIGIFARM_SMS_GATEWAY_URL
    DIGIFARM_PASSWORD = settings.DIGIFARM_PASSWORD

    class Meta:
        gateway_id = 1
        short_name = 'DF'
        verbose_name = 'Digifarm'

    def __init__(self, *args, **kwargs):
        self.gateway_kwargs = kwargs.copy()

        super(DigifarmGateway, self).__init__(*args, **kwargs)

        # initialise requests.Session with the required headers
        self.session = requests.Session()
        self.session.headers.update(
            {
                'Accept': 'application/json',
                'Authorization': f'Basic {self.DIGIFARM_PASSWORD}'
            }
        )

    def get_customer_filter_kwargs(self):
        return {'phone_number_hash__isnull': False, 'digifarm_farmer_id__isnull': False}

    def send_message(self, message: OutgoingSMS, recipient_ids: Union[QuerySet, list[int]], **kwargs: Any):
        if not settings.ENABLE_DIGIFARM_INTEGRATION:
            return
        from customers.models import Customer
        from sms.models import SMSRecipient
        payload = []
        customers_map = {}
        recipients = Customer.objects.filter(id__in=recipient_ids)

        for customer in recipients:
            digifarm_farmer_id = customer.digifarm_farmer_id
            blocked_user_cache_key = f'digifarm_blocked_{digifarm_farmer_id}'
            if cache.get(blocked_user_cache_key, False):
                logger.debug(f"digifarm.send_bulk_sms cache blocked: digifarm_id: {digifarm_farmer_id}")
                continue

            current_subscription = customer.current_subscription
            if not current_subscription:
                continue

            if current_subscription.is_premium:
                message_type = "Advisory Premium"
            else:
                message_type = "Advisory Freemium"

            payload.append(
                {
                    "farmerId": digifarm_farmer_id,
                    "messageType": message_type,
                    "messageContent": message.text,
                    "subscriptionReference": current_subscription.id
                }
            )
            customers_map[digifarm_farmer_id] = customer.id

        response = None
        try:
            response = self.session.post(
                self.SMS_ENDPOINT,
                json=payload,
                timeout=15
            )
            if response:
                logger.debug(f"digifarm.send_bulk_sms: digifarm_id: {digifarm_farmer_id}, status: {response.status_code}")
            else:
                logger.debug(f"digifarm.send_bulk_sms: digifarm_id: {digifarm_farmer_id}, response: None")
            response.raise_for_status()
        except requests.RequestException as e:
            # If response code is 422 it means the user has not provided consent to be spammed.
            # Response 401 has been showing up as well, but only for certain farmers. We assume
            # it is being used similarly.
            # We have no mechanism to check whether that consent is provided in future, so
            # just remember this for a sufficiently long period (30 days).
            if response:
                logger.debug(f"digifarm.send_bulk_sms exception, status: {response.status_code}")
            else:
                logger.debug(f"digifarm.send_bulk_sms exception, response: None")

            if response is not None and response.status_code in (401, 422):
                cache.set(blocked_user_cache_key, True, 2592000)
                logger.debug(f"digifarm.send_bulk_sms blocking user")
            elif response is not None and response.status_code == 400:
                cache.set(blocked_user_cache_key, True, 2592000)
                logger.debug(f"digifarm.send_bulk_sms blocking user")
                logger.debug(f"digifarm.send_bulk_sms, details: {response.json()}")
            else:
                logger.exception(
                    "Failed to send sms",
                    extra={
                        "digifarm_farmer_id": digifarm_farmer_id,
                        "text": message.text,
                        "response_text": response.text if response is not None else None
                    })
            return

        if response is not None:
            response_data = response.json()
            for item in response_data:

                if item['result'] == 'success':
                    delivery_status = 'Success'
                elif item['result'] == 'failure':
                    delivery_status = 'Failed'
                elif item['result'] == 'blocked':
                    delivery_status = 'Blocked'
                else:
                    delivery_status = 'Unknown'

                gateway_msg_id = item['outboundSmsResultId']

                SMSRecipient.objects.get_or_create(
                    recipient_id=customers_map[item['farmerId']],
                    message=message,
                    defaults=dict(
                        gateway_msg_id=gateway_msg_id,
                        delivery_status=delivery_status,
                        failure_reason=response.status_code,
                        page_index=1,  # It appears that digifarm does pagination in their network. We don't pre-paginate.
                        extra={},
                    )
                )
