from decouple import config

PLANTVILLAGE = {
    'username': config('PLANTVILLAGE_USERNAME'),
    'password': config('PLANTVILLAGE_PASSWORD'),
    'endpoint': config('PLANTVILLAGE_ENDPOINT'),
}
