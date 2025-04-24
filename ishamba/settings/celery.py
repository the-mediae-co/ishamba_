from decouple import config
from celery.schedules import crontab

# Celery config
# -----------------------------------------------------------------------------
TIME_ZONE = config('TIME_ZONE')
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'fanout_prefix': True,
    'fanout_patterns': True
}
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 300 * 1024  # 300MB in kilobytes

CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ACCEPT_CONTENT = {'pickle', 'json'}

# allows tests and mocking
DIGIFARM_WEATHER_CELERY_TASK = config('DIGIFARM_WEATHER_CELERY_TASK')

CELERY_BEAT_SCHEDULE = {
    'end-subscriptions-every-day': {
        'task': 'customers.tasks.end_subscriptions',
        'schedule': crontab(hour=8, minute=30),
    },

    # NOTE(apryde): Market price sending disabled as we have stopped recieving
    # market price data from the provider (gov agency).

    # 'send-premium-market-prices-every-monday': {
    #     'task': 'markets.tasks.send_premium_market_prices',
    #     'schedule': crontab(hour=12,
    #                         minute=0,
    #                         day_of_week='mon'),
    # },
    # 'send-digifarm-market-prices-every-monday': {
    #     'task': 'markets.tasks.send_digifarm_market_prices',
    #     'schedule': crontab(hour=12,
    #                         minute=30,
    #                         day_of_week='mon'),
    # },

    'send-tips-every-day': {
        'task': 'tips.tasks.send_scheduled_tips',
        'schedule': crontab(hour=13, minute=0),
    },

    # 'end-tip-subscriptions-every-day': {
    #     'task': 'tips.tasks.end_series_subscriptions',
    #     'schedule': crontab(hour=9, minute=30),
    # },

    # NOTE(apryde): Weather forcasts are currently sent manually every other
    # Wednesday via django management command.

    # 'try-sending-kenmet-weather-forecasts-every-day': {
    #     'task': 'weather.tasks.send_weather_forecasts',
    #     'schedule': crontab(hour=14, minute=0),
    # },

    'update_dailyoutgoingsmssummaries-each-day': {
        'task': 'sms.tasks.update_dailyoutgoingsmssummaries',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'clear_all_call_states-each-night': {
        'task': 'calls.tasks.clear_all_call_states',
        'schedule': crontab(hour=3, minute=12),  # Daily at 3:12am
    },
    'send-nps-query-each-morning': {
        'task': 'sms.tasks.send_nps_queries',
        'schedule': crontab(hour=9, minute=17),
        'args': ('ishamba', 200)
    },
}

CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
CELERY_BROKER_URL=config('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND=config('CELERY_RESULT_BACKEND')
