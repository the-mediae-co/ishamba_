import datetime
from typing import Optional
from ninja import Field, Schema

from core.constants import LANGUAGES, PHONE_TYPES, SEX


class CustomerSchema(Schema):
    id: int
    dob: Optional[datetime.date] = None
    name: str
    sex: Optional[SEX] = None
    relationship_status: Optional[str] = None
    phone_number_hash: Optional[str] = None
    digifarm_farmer_id: Optional[str] = None
    border0_id: Optional[int] = None
    border1_id: Optional[int] = None
    border2_id: Optional[int] = None
    border3_id: Optional[int] = None
    agricultural_region_id: Optional[int] = None
    weather_area_id: Optional[int] = None
    village: Optional[str] = None
    postal_address: Optional[str] = None
    postal_code: Optional[str] = None
    preferred_language: Optional[LANGUAGES] = None
    phone_type: Optional[PHONE_TYPES] = None
    join_method: Optional[str] = None
    stop_method: Optional[str] = None
    is_registered: bool
    has_requested_stop: bool
    stop_date: Optional[datetime.date] = None
    farm_size: Optional[str] = None
    owns_farm: Optional[bool] = None
    categories: list[int]
    commodities: list[int]
    tips_commodities: list[int]
    subscription_type: Optional[int] = None
    call_center: Optional[int] = None


class CustomerFetchResponse(Schema):
    items: list[CustomerSchema]
    page: int
    size: int
    next_page: Optional[int] = None
    prev_page: Optional[int] = None
    total_count: int


class CustomerFilters(Schema):
    page: int = Field(1)
    size: int = Field(12)
    tips_commodity: Optional[int] = None
    subscribed_to_tips: Optional[bool] = None

