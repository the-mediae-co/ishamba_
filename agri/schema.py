from typing import Optional

from ninja import Field, Schema

from agri.constants import COMMODITY_TYPES


class CommoditySchema(Schema):
    id: int
    name: str
    commodity_type: COMMODITY_TYPES
    variant_of_id: Optional[int] = Field(None, description='Parent commodity')
    seasonal_length_days: Optional[int] = Field(None, description='Length of season in days')
    tips_count: int
    call_center_tips_count: Optional[int]
    tips_enabled: bool
