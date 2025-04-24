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

from django.conf import settings
from decouple import config

DEBUG = False
TEST = True
MUTE_SMS = False
SECRET_KEY = config('SECRET_KEY', default='foobar')

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'basecamp',
    }
}

# we want to run tests with IP filtering on
IP_AUTHORIZATION = True

AUTHORIZED_IPS = config('AUTHORIZED_IPS', [], cast=lambda v: [s.strip() for s in v.split(',')])

# In testing, remove the local IP's so we can test unauthorized access
if not DEBUG:
    for addr in config('INTERNAL_IPS'):
        if addr in AUTHORIZED_IPS:
            AUTHORIZED_IPS.remove(addr)

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'select2': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}

SELECT2_CACHE_BACKEND = 'select2'

CLIENT_SETTINGS = {
    'fast_test': {
        'NAME': 'iShamba',
        'LOGO': 'images/ishamba/logo.png',
        'DOMAIN': 'https://test.com',
        'ACCEPT_ONLY_REGISTERED_CALLS': False,
        'SMS_SHORTCODE': 12345,
        'MPESA_TILL_NUMBER': '45678',
        'MONTH_PRICE': '95 kshs',
        'YEAR_PRICE': '800 kshs',
        'VOICE_QUEUE_NUMBER': '+254123456780',
        'VOICE_DEQUEUE_NUMBER': '+25487654321',
        'TIPS_REPORT': {
            'to': [
                'elizabeth@mediae.org',
            ],
        },
        'PUSHER_APP_ID': "106560",  # Use the Pusher staging channel for testing
        'PUSHER_KEY': "fbc04b3d2479e08f8bdc",
        'PUSHER_SECRET': "f964076910d28a82e5cb",
        'HOLD_RECORDING': 'calls/audio/ishamba/hold.mp3',
        'INACTIVE_RECORDING': 'calls/audio/ishamba/inactive.mp3',
        'CLOSED_RECORDING': 'calls/audio/ishamba/closed.mp3',
        'PREMIUM_ONLY_RECORDING': 'calls/audio/ishamba/premium_only.mp3',
        'SEND_WEATHER': True,
        'PLANTVILLAGE': {
            'endpoint': 'http://localhost/fakeurl',
            'username': 'mock',
            'password': 'mock',
            'batch_size': 100,
        },
        'MONTHLY_PRICE': 10.0,
    },
}

GATEWAY_SETTINGS = {
    'AT': {
        'senders': [
            {
                'country': 'Kenya',
                'senders': ['21606', 'iShamba']
            },
            {
                'country': 'Uganda',
                'senders': ['iShambaU']
            },
        ]
    },
    'DF': {
        'senders': [],
    }
}

GATEWAY_SECRETS = {
    'ATZMB': {
        'default': {
            'username': 'fake_username',
            'api_key': 'fake_api_key',
            'sender': 'iMunda',
        },
    },
    'AT': {
        'default': {
            'username': 'fake_username',
            'api_key': 'fake_api_key',
            'sender': '11111',
        },
        'test': {
            'username': 'test_username',
            'api_key': 'test_api_key',
            'sender': '22222',
        },
        'test1': {
            'username': 'test1_username',
            'api_key': 'test1_api_key',
            'sender': '33333',
        },
        'fast_test': {
            'username': 'fast_test_username',
            'api_key': 'fast_test_api_key',
            'sender': '44444',
            'monthly_price': 10.0,
        },
    },
    'DF': {
        'default': {
            'username': 'ishamba',
            'api_key': 'not used',
            'sender': 'not used',
        }
    },
}

DIGIFARM_USERNAME = 'digifarm-user'
DIGIFARM_PASSWORD = 'digifarm-pass'
