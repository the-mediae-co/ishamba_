
from typing import Optional
from ninja import Field, Schema

from core.constants import LANGUAGES, PHONE_TYPES, SEX


class PaginatedResponseSchema(Schema):
    page: int
    size: int
    total_count: int
    next_page: Optional[int] = None
    previous_page: Optional[int] = None


class PaginatedFilterSchema(Schema):
    page: int = Field(1)
    size: int = Field(20)


class BaseMetaDataSchema(Schema):
    phone_types: dict[str, str] = dict(PHONE_TYPES.choices)
    sex: dict[str, str] = dict(SEX.choices)
    languages: list[dict[str, str]] = [{'label': choice.label, 'value': choice.value} for choice in
                                           LANGUAGES]
