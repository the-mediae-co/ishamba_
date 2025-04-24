# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0008_auto_20150112_0623'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='cost',
            field=models.FloatField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
