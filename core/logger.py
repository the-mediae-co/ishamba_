"""
To save a slight bit of repetition.

Usage:
    from core import log

    log.info(msg, extra={'extra_vars': vars})
"""
import logging


log = logging.getLogger('ishamba')


def enable_sql_logging():
    """ Enables logging of the SQL queries emitted by the Django ORM.
    """
    logger = logging.getLogger('django.db.backends')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
