
from datetime import datetime
from typing import Any
from ninja import Query, Router
from ninja.security import django_auth
from ninja.errors import HttpError

from customers.models import Customer, CustomerPhone
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import IncomingSMS, OutgoingSMS, SMSRecipient
from sms.schema import MetaDataSchema, OutgoingSMSCreateSchema, OutgoingSMSResponseSchema, OutgoingSMSSchema, OutgoingSMSFilterSchema, SMSRecipientFilterSchema, SMSRecipientResponseSchema
from sms.tasks import send_message


router = Router(tags=["sms"], auth=[django_auth])

SMS_TYPE_DISPLAY_LOOKUP = dict(OUTGOING_SMS_TYPE.choices)


@router.get("/metadata/")
def metadata(request) -> MetaDataSchema:
    return MetaDataSchema()


@router.get("outgoing_sms/", response=OutgoingSMSResponseSchema)
def fetch_outgoing_sms(request, filters: OutgoingSMSFilterSchema = Query(...)) -> dict[str, Any]:
    search = OutgoingSMS.search.sort('-created')
    if filters.message_type:
        search = search.filter('terms', message_type=filters.message_type)
    if filters.created_gt:
        search = search.filter('range', created={'gte': filters.created_gt})
    if filters.created_lt:
        search = search.filter('range', created={'lte': filters.created_lt})
    if filters.q:
        search = search.filter('match', text=filters.q)
    page_start = (filters.page - 1) * filters.size
    page_end = page_start + filters.size
    next_page = None
    previous_page = None
    if filters.page > 1:
        previous_page = filters.page - 1
    response = search[page_start: page_end].execute()
    if response.hits.total.value > page_end:
        next_page = filters.page + 1
    items = [hit.to_dict() for hit in response.hits]
    for item in items:
        item['message_type_display'] = SMS_TYPE_DISPLAY_LOOKUP.get(item['message_type'])
    return {
        'total_count': response.hits.total.value,
        'page': filters.page,
        'size': filters.size,
        'next_page': next_page,
        'previous_page': previous_page,
        'items': items
    }

@router.post("outgoing_sms/", response=OutgoingSMSSchema)
def create_outgoing_sms(request, data: OutgoingSMSCreateSchema) -> dict[str, Any]:
    sms = OutgoingSMS.objects.create(message_type=data.message_type, text=data.text)
    OutgoingSMS.es.indices.refresh()
    message_data = OutgoingSMS.from_index(sms.id)
    recipient_ids = Customer.objects.filter(id__in=data.customer_ids).values_list('id', flat=True)
    if recipient_ids:
        if data.eta:
            send_message.apply_async(
                {'sms_id': sms.id, 'recipient_ids': recipient_ids, 'sender': data.sender},
                eta=data.eta
            )
        else:
            send_message.delay(sms.id, recipient_ids=recipient_ids, sender=data.sender)
    message_data['message_type_display'] = SMS_TYPE_DISPLAY_LOOKUP.get(message_data['message_type'])
    return message_data


@router.get("outgoing_sms/{message_id}/", response=OutgoingSMSSchema)
def retrieve_outgoing_sms(request, message_id: int) -> dict[str, Any]:
    message_data = OutgoingSMS.from_index(message_id)
    message_data['message_type_display'] = SMS_TYPE_DISPLAY_LOOKUP.get(message_data['message_type'])
    return message_data


@router.get("sms_recipients/", response=SMSRecipientResponseSchema)
def fetch_sms_recipients(request, filters: SMSRecipientFilterSchema = Query(...)) -> dict[str, Any]:
    search = SMSRecipient.search.sort('-created')
    if filters.message_id:
        search = search.filter('term', message_id=filters.message_id)
    page_start = (filters.page - 1) * filters.size
    page_end = page_start + filters.size
    next_page = None
    previous_page = None
    if filters.page > 1:
        previous_page = filters.page - 1
    response = search[page_start: page_end].execute()
    if response.hits.total.value > page_end:
        next_page = filters.page + 1
    return {
        'total_count': response.hits.total.value,
        'page': filters.page,
        'size': filters.size,
        'next_page': next_page,
        'previous_page': previous_page,
        'items': [hit.to_dict() for hit in response.hits]
    }
