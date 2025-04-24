import time

import sentry_sdk
from django.db import connection

from celery.utils.log import get_task_logger
from django_tenants.utils import get_tenant_model, tenant_context

from ishamba.celery import app

from core.tasks import BaseTask
from calls.models import Call

logger = get_task_logger(__name__)


@app.task(base=BaseTask, ignore_result=False)
def clear_call_states():
    """
    Clear all calls with is_active=True or connected=True
    """
    schema_name = connection.schema_name

    tic = time.perf_counter()
    active_count = Call.objects.filter(is_active=True).update(is_active=False)
    connected_count = Call.objects.filter(connected=True).update(connected=False)
    toc = time.perf_counter()
    msg = (f"Cleared {active_count} active and {connected_count} connected Calls "
           f"for schema {schema_name} in {tic - toc:0.1f} seconds")
    logger.info(msg)
    if active_count > 0 or connected_count > 0:
        sentry_sdk.capture_message(msg)
    return True


@app.task(base=BaseTask, ignore_result=True)
def clear_all_call_states():
    """
    Celery.beat calls this task. Since tasks cannot be called per tenant schema,
    this method calls clear_call_states() for each schema separately.
    """
    for tenant in get_tenant_model().objects.exclude(schema_name='public'):
        with tenant_context(tenant):
            clear_call_states.delay()
