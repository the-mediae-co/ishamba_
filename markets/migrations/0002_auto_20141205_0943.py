# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='market',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(srid=4326, geography=True),
            preserve_default=True,
        ),
    ]
