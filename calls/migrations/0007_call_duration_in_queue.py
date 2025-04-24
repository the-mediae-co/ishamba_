# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0006_auto_20141230_1041'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='duration_in_queue',
            field=models.PositiveSmallIntegerField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
