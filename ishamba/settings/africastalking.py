from decouple import config
# IP Authorization
# -----------------------------------------------------------------------------
IP_AUTHORIZATION = config('IP_AUTHORIZATION', True, cast=bool)
DEBUG = config('DEBUG', False, cast=bool)

AUTHORIZED_IPS = config('AUTHORIZED_IPS', [], cast=lambda v: [s.strip() for s in v.split(',')])

if DEBUG:
    AUTHORIZED_IPS += ('127.0.0.1', '10.0.2.2')

# AfricasTalking gateway configuration
# -----------------------------------------------------------------------------
SMS_SENDER_AGRITIP = 'iShamba'
SMS_SENDER_DATA_QUERY = '21606'
SMS_SENDER_KENMET_FORECAST = 'iShamba'
SMS_SENDER_MARKET_PRICE = 'iShamba'
SMS_SENDER_SUBSCRIPTION = 'iShamba'
SMS_SENDER_VOUCHER_DEFAULT = 'iShamba'

# API
DEFAULT_AT_USERNAME = config('DEFAULT_AT_USERNAME')
DEFAULT_AT_API_KEY = config('DEFAULT_AT_API_KEY')
AT_SMS_ENDPOINT = config('AT_SMS_ENDPOINT', 'https://api.sandbox.africastalking.com/version1/messaging')
AT_VOICE_ENDPOINT = config('AT_VOICE_ENDPOINT', 'https://voice.sandbox.africastalking.com/call')
