# -*- coding: utf-8 -*-


from django.db import models, migrations


def create_regions(apps, schema_editor):
    pass


def reverse_create_regions(apps, schema_editor):
    """ The above is idempotent. Be lazy here.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0003_auto_20141218_1458'),
    ]

    operations = [
        migrations.RunPython(create_regions, reverse_create_regions),
    ]
