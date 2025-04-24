import datetime
from typing import Optional

from ninja import Field, Schema

from core.schema import BaseMetaDataSchema, PaginatedFilterSchema, PaginatedResponseSchema
from sms.constants import OUTGOING_SMS_TYPE


class MetaDataSchema(BaseMetaDataSchema):
    message_types: list[dict[str, str]] = [{'label': choice.label, 'value': choice.value} for choice in OUTGOING_SMS_TYPE]


class OutgoingSMSCreateSchema(Schema):
    text: str
    message_type: OUTGOING_SMS_TYPE = Field(OUTGOING_SMS_TYPE.BULK)
    customer_ids: list[int] = []
    sender: str = Field('21606')
    eta: Optional[datetime.datetime] = None


class OutgoingSMSSchema(OutgoingSMSCreateSchema):
    id: int
    sent_by_id: Optional[int] = None
    incoming_sms_id: Optional[int] = None
    created: datetime.datetime
    message_type_display: str


class OutgoingSMSResponseSchema(PaginatedResponseSchema):
    items: list[OutgoingSMSSchema]


class OutgoingSMSFilterSchema(PaginatedFilterSchema):
    message_type: Optional[list[OUTGOING_SMS_TYPE]] = None
    created_gt: Optional[datetime.datetime] = None
    created_lt: Optional[datetime.datetime] = None
    q: str = Field('')


class SMSRecipientFilterSchema(PaginatedFilterSchema):
    message_id: Optional[int]


class SMSRecipientSchema(Schema):
    id: int
    message_id: int
    recipient_id: int
    created: datetime.datetime
    gateway_name: str
    gateway_msg_id: Optional[str] = None
    delivery_status: str
    failure_reason: Optional[str] = None
    cost: float


class SMSRecipientResponseSchema(PaginatedResponseSchema):
    items: list[SMSRecipientSchema]
