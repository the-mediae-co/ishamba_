# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0015_auto_20150115_1417'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commoditysubscription',
            name='epoch_date',
            field=models.DateField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
