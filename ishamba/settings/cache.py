from decouple import config
CACHES = {
    # 'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'},
    'default': {
        # 'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL'),
        'KEY_FUNCTION': 'django_tenants.cache.make_key',
        'REVERSE_KEY_FUNCTION': 'django_tenants.cache.reverse_key',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'default',
    },
    'select2': {
        # 'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL'),
        'KEY_FUNCTION': 'django_tenants.cache.make_key',
        'REVERSE_KEY_FUNCTION': 'django_tenants.cache.reverse_key',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'select2',
        'TIMEOUT': 60 * 60 * 12,  # 12 hours
    },
}

SELECT2_CACHE_BACKEND='select2'

REDIS_MISC_URL = ''
