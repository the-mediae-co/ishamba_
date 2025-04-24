# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0036_auto_20150828_1101'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='sex',
            field=models.CharField(blank=True, max_length=8, null=True, verbose_name='sex', choices=[(b'f', b'Female'), (b'm', b'Male')]),
        ),
    ]
