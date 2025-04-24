from typing import Optional
from ninja import Schema


class CallCenterOperatorSchema(Schema):
    id: int
    call_center_id: int
    name: str
    border_id: int
    sender_id: Optional[str] = None
    current: bool
