from enum import Enum
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from core.models import TimestampedBase


class InterrogationSession(TimestampedBase):
    class SessionType(Enum):
        REGISTRATION = 0
        SURVEY = 1

    phone = PhoneNumberField(db_index=True)
    session_type = models.IntegerField(default=SessionType.REGISTRATION.value)
    # pickled state of the current session
    session_mgr = models.BinaryField()
    # whether the session is finished (no more questions to ask)
    finished = models.BooleanField(default=False)
