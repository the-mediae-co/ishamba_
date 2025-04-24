from functools import wraps

import redis
import redis_lock
from celery.utils.log import get_task_logger
from django.conf import settings

LOGGER = get_task_logger(__name__)

_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.REDIS_MISC_URL)
    return _redis_client


def only_one(key="", expire=60, auto_renewal=True, default_ret_value=None):
    """
    Enforce only one celery task at a time.
    See: http://loose-bits.com/2010/10/distributed-task-locking-in-celery.html
    """

    def _dec(run_func):
        """Decorator."""

        @wraps(run_func)
        def _caller(*args, **kwargs):
            """Caller."""
            ret_value = default_ret_value
            have_lock = False
            lock = redis_lock.Lock(get_redis_client(), name=key, expire=expire, auto_renewal=auto_renewal)
            try:
                have_lock = lock.acquire(blocking=False)
                if have_lock:
                    ret_value = run_func(*args, **kwargs)
                else:
                    LOGGER.info(f'Skipping task due to lock {key} being held')
            finally:
                if have_lock:
                    lock.release()

            return ret_value

        return _caller

    return _dec
