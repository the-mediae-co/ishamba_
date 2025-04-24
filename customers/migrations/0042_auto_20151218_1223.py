# -*- coding: utf-8 -*-


from django.db import migrations, models

def update_task_statuses(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
    expects.
    """
    Task = apps.get_model("customers", "Task")
    TaskUpdate = apps.get_model("customers", "TaskUpdate")

    for t in Task.objects.exclude(taskupdate=None).prefetch_related('taskupdate_set'):
        t.status = t.taskupdate_set.latest('created').status
        t.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0041_task_status'),
    ]

    operations = [
        migrations.RunPython(update_task_statuses, None),
    ]
