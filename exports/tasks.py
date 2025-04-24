import tempfile

from celery import Task

from django.db import connection
from django.core.files.storage import default_storage
from django.contrib.staticfiles import finders
from django.utils.timezone import localtime, now

from celery.utils.log import get_task_logger
from PIL import Image
from django_tenants.utils import schema_context

from ishamba.celery import app

from .models import Export, MapExport

logger = get_task_logger(__name__)


class BaseExportTask(Task):
    """ Abstract base `celery.Task` for the generation of exports.
    """
    abstract = True

    def export(self, pk):
        """ Generates the export.

        Args:
            pk (int): The primary key of the Export to be generated.
        """

        # load export
        try:
            export = Export.objects.get(pk=pk)
        except Export.DoesNotExist as e:
            logger.exception(e, exc_info=True)

        # check export is either queued or failed
        if export.status not in (Export.STATUS.queued, Export.STATUS.failed):
            logger.warn(
                'Tried to start an export with status: {}. Skipping.'.format(
                    export.get_status_display()
                )
            )
            return

        # mark the export as started
        export.status = Export.STATUS.started
        export.started_at = localtime(now())
        export.save(update_fields=['status', 'started_at'])

        try:
            # generate filename
            export.exported_file = export.generate_filename()
            # open file for writing
            with tempfile.TemporaryFile('w+b') as f:
                cursor = connection.cursor()
                query, params = export.export_sql_with_params()
                raw_query = cursor.mogrify(query, params)
                cursor.copy_expert(raw_query, f)
                default_storage.save(export.exported_file, f)
        except Exception:
            logger.exception('Export task failed', extra={'export_pk': export.pk})
            export.status = Export.STATUS.failed
        else:
            export.status = Export.STATUS.complete

        export.completed_at = localtime(now())
        export.save(update_fields=['status', 'completed_at', 'exported_file'])


@app.task(base=BaseExportTask, bind=True)
def generate_export(self, pk, client):
    """ Utilises Mediae CRM's `BaseExportTask` to generate exports
    """
    with schema_context(client):
        self.export(pk)


@app.task(base=BaseExportTask, bind=True)
def generate_map(self, pk, client):
    with schema_context(client):
        try:
            export = MapExport.objects.get(pk=pk)
        except MapExport.DoesNotExist as e:
            logger.exception(e, exc_info=True)

        # check export is either queued or failed
        if export.status not in (Export.STATUS.queued, Export.STATUS.failed):
            logger.warn(
                'Tried to start an export with status: {}. Skipping.'.format(
                    export.get_status_display()
                )
            )
            return

        # mark the export as started
        export.status = Export.STATUS.started
        export.started_at = localtime(now())
        export.save(update_fields=['status', 'started_at'])

        try:
            # generate filename
            export.map_file = export.generate_filename()

            config = export.get_map_config()
            map_image = export.make_map_image(config)
            # Find the key
            map_key_path = finders.find('img/map_key.png')
            # If we do not find a key, just don't add one
            if map_key_path:
                map_key = Image.open(map_key_path)
                # Work out coordinates for bottom right, with a 10px buffer
                x = map_image.width - map_key.width - 10
                y = map_image.height - map_key.height - 10
                # Check we are inside bounds
                if x and y:
                    # Overlay the key
                    map_image.paste(map_key, (x, y), map_key)
            with tempfile.TemporaryFile('w+b') as fh:
                map_image.save(fh, format='png')
                default_storage.save(export.map_file, fh)

        except Exception as e:
            logger.warn(e.message,
                        exc_info=True,
                        extra={'export_pk': export.pk})
            export.status = Export.STATUS.failed
        else:
            export.status = Export.STATUS.complete

        export.completed_at = localtime(now())
        export.save(update_fields=['status', 'completed_at', 'map_file'])
