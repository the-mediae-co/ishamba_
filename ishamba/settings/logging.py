def skip_incorrect_worker_rss_error(record):
    """
    Billiard incorrectly logs ERROR 'worker unable to determine memory usage'
    when billiard.pool.Worker.max_memory_per_child is set.
    See: https://github.com/celery/billiard/issues/205 for details.
    """
    return record.getMessage() == 'worker unable to determine memory usage'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'syslog'],
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'skip_incorrect_worker_rss_error': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': skip_incorrect_worker_rss_error,
        }
    },
    'formatters': {
        'verbose': {
            'format': '[%(levelname)s] %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '[%(levelname)s] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'syslog': {
            'filters': ['require_debug_false'],
            'class': 'logging.handlers.SysLogHandler',
            'address': '/dev/log',
        }
    },
    'loggers': {
        # Work around for https://github.com/ipython/ipython/issues/10946
        'parso': { 'handlers': ['console'], 'level': 'INFO', 'propagate': False, },
        'asyncio': {
            'level': 'WARNING',
        },
        'django': {
            'handlers': ['console'],
            'propagate': True,
        },
        'ishamba': {
            'handlers': ['console', 'syslog'],
            'level': 'DEBUG'
        },
        'multiprocessing': {
            'handlers': ['console'],
            'level': 'WARN',
            'filters': ['skip_incorrect_worker_rss_error'],
        },
        'django.request': {
            'handlers': ['syslog'],
            'level': 'ERROR',
            'propagate': False,
        },
        'markets.tasks': {
            'handlers': ['syslog'],
            'level': 'WARN',
            'propagate': True,
        },
        'weather.tasks': {
            'handlers': ['syslog'],
            'level': 'WARN',
            'propagate': True,
        }
    }
}
