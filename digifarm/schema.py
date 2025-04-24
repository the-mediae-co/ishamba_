import datetime
import pydantic
from typing import Any, Literal, Optional, Union
from pydantic import field_validator, model_validator

from ninja import Field, Schema

from agri.constants import COMMODITY_TYPES
from agri.models import Commodity
from core.constants import LANGUAGES, PHONE_TYPES, SEX
from core.schema import BaseMetaDataSchema
from world.models import Border


class BorderSchema(Schema):
    id: int
    name: str


class ValueChainSchema(Schema):
    commodity: int
    date_planted: Optional[datetime.date] = Field(None, description="Planting Date for crop type")

    @field_validator('commodity')
    @classmethod
    def validate_commodity(cls, value: int) -> int:
        if not Commodity.objects.filter(id=value).exists():
            raise ValueError("Invalid commodity")
        return value

class FarmerSubscriptionSchema(Schema):
    reference: Optional[str] = Field("", description="The reference of the subscription object in digifarm")
    expiry_date: Optional[datetime.date] = Field(None, description="When the subscription expires")
    subscription_type: Optional[Literal['freemium', 'premium']] = Field("freemium", description="The subscription tier of the farmer")
    ishamba_id: Optional[int] = Field(None, description="The reference of the subscription object in ishamba")

    @model_validator(mode="after")
    @classmethod
    def validate_subscription_info(cls, values):
        if values.subscription_type == 'premium' and not values.expiry_date:
            raise ValueError("Expiry date is required for premium subscription")

        return values


class FarmerSyncSchema(Schema):
    phone_number_hash: str = Field(description="sha256 hash of the farmer's phone number in intl format")
    name: str = Field("", description="The name of the farmer", max_length=120)
    digifarm_farmer_id: str
    sex: Optional[Union[SEX, Literal[""]]] = Field("", description="Optional sex of the farmer")
    dob: Optional[datetime.date] = Field(None, description="Optional date of birth of the farmer")
    postal_address: Optional[str] = Field("", description="Optional postal address of the farmer")
    postal_code: Optional[str] = Field("", description="Optional postal code of the farmer")
    ward: int
    value_chains: list[ValueChainSchema]  # commodities
    preferred_language: Optional[LANGUAGES] = Field(LANGUAGES.ENGLISH, description="preferred language for sms delivery")
    phone_type: Optional[PHONE_TYPES] = Field(None, description="Smart Phone, Feature phone or basic phone?")
    subscription: FarmerSubscriptionSchema = Field(description="Farmer subscription Information ")

    @field_validator('ward')
    @classmethod
    def validate_ward(cls, value: int) -> int:
        if not Border.objects.filter(id=value, country='Kenya', level=3).exists():
            raise ValueError("Invalid ward")
        return value


class FarmerSyncSuccessResponse(Schema):
    phone_number_hash: str
    digifarm_farmer_id: str
    ishamba_farmer_id: int
    subscription: FarmerSubscriptionSchema


class FarmerSyncErrorResponse(Schema):
    phone_number_hash: str
    digifarm_farmer_id: str
    error_detail: str


class FarmerBulkSyncSchema(Schema):
    farmers: list[FarmerSyncSchema]

    @model_validator(mode="after")
    @classmethod
    def validate_batch(cls, values):
        num_of_farmers = len(values.farmers)
        if num_of_farmers == 0:
            raise ValueError("You must sync at least one farmer")
        if num_of_farmers > 20:
            raise ValueError("You are only allowed 20 farmers at a time for bulk sync")
        return values


class FarmerBulkSyncResponse(Schema):
    synced: list[FarmerSyncSuccessResponse]
    errors: list[FarmerSyncErrorResponse]


class MetaDataSchema(BaseMetaDataSchema):
    commodity_types: dict[str, str] = dict(COMMODITY_TYPES.choices)
