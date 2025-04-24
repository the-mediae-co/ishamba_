# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0005_task_taskupdate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(srid=4326, geography=True),
            preserve_default=True,
        ),
    ]
