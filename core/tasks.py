from celery import Task
from celery.utils.log import get_task_logger
from tenant_schemas_celery.task import TenantTask

from ishamba.celery import app


logger = get_task_logger(__name__)


class BaseTask(TenantTask):
    retry_strategy = 0

    def on_failure(self, exc, *args, **kwargs):
        """ Log exception on failure. """
        logger.exception(exc)
        super().on_failure(exc, *args, **kwargs)


@app.task(base=BaseTask)
def test_task():
    logger.info("I am a test task")
