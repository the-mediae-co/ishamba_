import os

from django.conf import settings  # noqa
from tenant_schemas_celery.app import CeleryApp

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ishamba.settings')

app = CeleryApp('ishamba')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
