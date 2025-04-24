import datetime
from typing import Any, Optional
from ninja import Schema

from core.constants import LANGUAGES


class TipTranslationSchema(Schema):
    id: Optional[int] = None
    text: str
    language: LANGUAGES


class TipSchema(Schema):
    id: int
    delay_days: int
    translations: list[TipTranslationSchema]
    commodity_id: int


class TipCreateSchema(Schema):
    delay_days: int
    translations: list[TipTranslationSchema]


class TipsUploadSchema(Schema):
    commodity_id: int
    tips: list[TipCreateSchema]


class TipSeasonSchema(Schema):
    id: Optional[int] = None
    commodity_id: int
    start_date: datetime.date
    customer_filters: dict[str, Any]


class BulkTipSeasonsSchema(Schema):
    seasons: list[list[str]]
