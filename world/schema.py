from typing import Optional
from ninja import Schema


class BorderLevelSchema(Schema):
    id: int
    name: str
    level: int
    country: str


class BorderLevelFilters(Schema):
    level: Optional[int] = None
    country: Optional[str] = None


class BorderFilters(Schema):
    level: Optional[int] = None
    name: Optional[str] = None
    country: Optional[str] = None
    parent: Optional[int] = None
    search: Optional[str] = None


class BorderSchema(Schema):
    id: int
    parent_id: Optional[int] = None
    country: str
    name: str
