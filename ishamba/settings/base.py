from os import path
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from decouple import config

from django.contrib.gis.measure import Distance

from core.api.utils import get_user_secret

PROJECT_ROOT = path.dirname(path.dirname(path.dirname(path.abspath(__file__))))

PROJECT_NAME = 'iShamba'

DEBUG = config('DEBUG', False, cast=bool)

SECRET_KEY = config('SECRET_KEY')

ADMINS = (('iShamba Dev', 'elizabeth@mediae.org'),)

ORIGINAL_BACKEND = 'django.contrib.gis.db.backends.postgis'

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

# https://django-tenants.readthedocs.io/en/latest/use.html?highlight=TENANT_LIMIT_SET_CALLS#performance-considerations
PG_EXTRA_SEARCH_PATHS = ['extensions']

TENANT_LIMIT_SET_CALLS = True

if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

sentry_sdk.init(
    dsn=config('SENTRY_DSN', ''),
    integrations=[DjangoIntegration(), CeleryIntegration(), RedisIntegration()],
    environment=config('SENTRY_ENVIRONMENT', 'development'),
    send_default_pii=True,
)

# Installed apps
# -----------------------------------------------------------------------------
DJANGO_APPS = [
    'django_tenants',  # Needs to be listed here for ./manage.py commands
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.contrib.humanize',
    'django_filters',
]

THIRD_PARTY_APPS = [
    'actstream',
    'crispy_forms',
    'django_extensions',
    'django_redis',
    'django_s3_storage',
    'django_tables2',
    'djangoql',
    'import_export',
    'rest_framework',
    'taggit',
    'durationwidget',
    'django.contrib.admin',
    'django_select2',
]

LOCAL_APPS = [
    'agri',
    'calls',
    'core',
    'customers',
    'digifarm',
    'exports',
    'gateways',
    'interrogation',
    'markets',
    'payments',
    'sms',
    'tasks',
    'tips',
    'weather',
    'world',
    'callcenters',
    'subscriptions',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
if DEBUG:
    INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar']
    DEBUG_TOOLBAR_CONFIG = {
        'INTERCEPT_REDIRECTS': False,
    }

# Separate from INSTALLED_APPS for Django, the SHARED_APPS and TENANT_APPS lists
# need to define the configuration (public vs per-schema) of each app for django-tenants.

# SHARED_APPS lists the apps that apply to the 'public' schema
SHARED_APPS = (
    'django_tenants',  # Needs to come first, and needs to be listed both here AND in DJANGO_APPS.
    'core',
    'world',
)

# TENANT_APPS lists the apps that apply to each tenant schema
TENANT_APPS = (
    'actstream',
    'agri',
    'callcenters',
    'calls',
    'customers',
    'exports',
    'interrogation',
    'markets',
    'payments',
    'sms',
    'tasks',
    'tips',
    'taggit',
    'weather',
    'subscriptions',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
)

# https://django-tenants.readthedocs.io/en/latest/install.html#configure-tenant-and-shared-applications
TENANT_MODEL = 'core.Client'
TENANT_DOMAIN_MODEL = 'core.Domain'

# Internationalisation
# -----------------------------------------------------------------------------
TIME_ZONE = config('TIME_ZONE')

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-gb'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

MIDDLEWARE = (
    'django_tenants.middleware.TenantMainMiddleware',  # MUST be listed first so that replacing with debugging version is possible
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'ishamba.middleware.IPMonitorMiddleware',
)

if DEBUG:
    MIDDLEWARE = MIDDLEWARE + (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
        'request_logging.middleware.LoggingMiddleware',
    )
    # https://django-tenant-schemas.readthedocs.io/en/latest/advanced_usage.html
    # Since only one BaseTenantMiddleware subclass is allowed per project, we
    # replace TenantMiddleware with the debugging version here
    MIDDLEWARE = ('core.tenant_middleware.DebuggingTenantMiddleware',) + MIDDLEWARE[1:]

ROOT_URLCONF = 'ishamba.urls'

LOGIN_REDIRECT_URL = '/'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'ishamba.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            path.join(PROJECT_ROOT, 'templates'),
            path.join(PROJECT_ROOT, 'frontend', 'static'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'callcenters.context_processors.my_call_centers',
            ]
        },
    },
]

# Django 3.x requires the automatically generated pk to be declared
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Email settings
# -----------------------------------------------------------------------------
EMAIL_HOST = config("EMAIL_HOST")
SERVER_EMAIL = "admin@portal.ishamba.com"
DEFAULT_FROM_EMAIL = "admin@portal.ishamba.com"
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_USE_TLS = True
# EMAIL_PORT = 587
# Override this in local settings for staging etc.
EMAIL_SUBJECT_PREFIX = f'[{PROJECT_NAME}] '
EMAIL_ATTACHMENT_ARCHIVE_ROOT = path.join(PROJECT_ROOT, 'archive')
EMAIL_ATTACHMENT_ARCHIVE_MAX_FILES = 50

# Static / media
# -----------------------------------------------------------------------------

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = path.join(PROJECT_ROOT, 'media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
STATIC_ROOT = path.join(PROJECT_ROOT, 'static')

# URL prefix for static files.
STATIC_URL = '/static/'


STATICFILES_DIRS = [
    path.join(PROJECT_ROOT, 'frontend', 'static')
]

# django-import-export
# -----------------------------------------------------------------------------
IMPORTER_RAISE_ERRORS = False
MARKET_PRICE_IMPORT_FOLDER = path.join(PROJECT_ROOT, 'tmp')
MARKET_PRICE_FILENAME_TEMPLATE = '{year}{month}{day}.csv'
MARKET_PRICE_IMPORT_RETRY_INTERVAL = 60  # minutes
MARKET_PRICE_IMPORT_MAX_ATTEMPTS = 10
IMPORTER_FUZZY_MATCH_SCORE_CUTOFF = 90
# whether to import customer records which match existing records
CUSTOMER_IMPORT_PERMIT_UPDATE = False

# crispy forms
# -----------------------------------------------------------------------------
CRISPY_TEMPLATE_PACK = 'bootstrap4'

JQUERY_URL = None

# Leaflet config
# -----------------------------------------------------------------------------
LEAFLET_CONFIG = {
    'PLUGINS': {
        'forms': {
            'auto-include': True,
            'css': ['https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.css'],
            'js': ['https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.js'],
        }
    },
    'FORCE_IMAGE_PATH': True,
    'DEFAULT_CENTER': (0.2636709443366501, 37.4853515625),
    'DEFAULT_ZOOM': 6,
}

# django-taggit
# -----------------------------------------------------------------------------
TAGGIT_CASE_INSENSITIVE = True

# Customers
# -----------------------------------------------------------------------------
CUSTOMERS_SUBSCRIPTION_DEFAULTS = {
    'is_permanent': True,
}
CUSTOMERS_SUBSCRIPTION_DEFAULT_ALLOWANCES = {
    'markets': 2,
    'tips': 2,
    'prices': 2,
}

# Django REST framework
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'JWT_VERIFY_EXPIRATION': False,
    'JWT_GET_USER_SECRET_KEY': get_user_secret,
}

# World
# -----------------------------------------------------------------------------
WORLD_COUNTY_DISTANCE_CUTOFF = Distance(km=10)

# Activity Stream
# -----------------------------------------------------------------------------
ACTSTREAM_SETTINGS = {
    'USE_JSONFIELD': True
}

USE_NATIVE_JSONFIELD = True  # Was used for django-jsonfield-compat, but no longer needed?

# Mediae CRM
# -----------------------------------------------------------------------------
MCRM_SMS_INCOMINGSMS_MODEL = 'sms.IncomingSMS'

# Additional convenience packages to always have shell_plus load
SHELL_PLUS_IMPORTS = [
    'from datetime import date, time, datetime, timedelta',
    'import zoneinfo',
    'from django.utils import timezone',
    'import csv',
    'import json',
    'from sms.constants import *',
    'from django.db.models import F, Q, Case, When, Sum, Count',
]

USE_S3_FILE_STORAGE = config('USE_S3_FILE_STORAGE', False, cast=bool)

if USE_S3_FILE_STORAGE:
    DEFAULT_FILE_STORAGE = 'core.storage.S3TenantStorage'
    AWS_REGION = "eu-west-1"
    AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL')
    AWS_S3_BUCKET_AUTH = True
    AWS_S3_MAX_AGE_SECONDS = 60 * 60
    AWS_S3_ENCRYPT_KEY = True
    AWS_S3_BUCKET_NAME = config('AWS_S3_BUCKET_NAME')
else:
    DEFAULT_FILE_STORAGE = 'django_tenants.storage.TenantFileSystemStorage'

AWS_ACCESS_KEY_ID=config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY=config('AWS_SECRET_ACCESS_KEY')

# pusher defaults
DEFAULT_PUSHER_KEY=config('DEFAULT_PUSHER_KEY')
DEFAULT_PUSHER_SECRET=config('DEFAULT_PUSHER_SECRET')
DEFAULT_PUSHER_APP_ID=config('DEFAULT_PUSHER_APP_ID')

# Elasticsearch
ELASTICSEARCH = {
    "default": {
        "host": config('ELASTICSEARCH_HOST'),
        "timeout": 60
    }
}
INDEX_PREFIX = config('INDEX_PREFIX')
CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_HTTPONLY = False  # False since we will grab it via universal-cookies
SESSION_COOKIE_HTTPONLY = True

# CIAT Diet Quality Survey Configuration
CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS = config(
    'CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS', default=16000, cast=int)

# Set specific limits for males and females
CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS_PER_GENDER_MALE = config(
    'CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS_PER_GENDER_MALE', default=13000, cast=int)

CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS_PER_GENDER_FEMALE = config(
    'CIAT_DIET_QUALITY_SURVEY_MAX_RESPONDENTS_PER_GENDER_FEMALE', default=6000, cast=int)

# AWS BEDROCK
AWS_BEDROCK_REGION = config('AWS_BEDROCK_REGION', default='eu-west-2')
LLM_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'
LLM_TEMPERATURE = 0

SIGNUP_AI_AGENT_WHITELIST_ENABLED = config('SIGNUP_AI_AGENT_WHITELIST_ENABLED', default=False, cast=bool)
SIGNUP_AI_AGENT_WHITELISTED_NUMBERS = config('SIGNUP_AI_AGENT_WHITELISTED_NUMBERS',
                                             cast=lambda v: [s.strip() for s in v.split(',')],
                                             default='')
