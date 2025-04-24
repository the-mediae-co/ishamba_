# Import the defaults and common settings
from .base import *  # noqa: F401, F403
from .logging import *
from .sms import *
from .tasks import *
from .africastalking import *
from .celery import *
from .cache import *
from .db import *
from .plant_village import *
from .digifarm import *

try:
    from .local import *
except ImportError:
    pass
