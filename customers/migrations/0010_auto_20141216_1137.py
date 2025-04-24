# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0009_auto_20141216_1023'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commoditysubscription',
            name='epoch_date',
            field=models.DateField(null=True),
            preserve_default=True,
        ),
    ]
