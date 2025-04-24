# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0035_auto_20150708_1011'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='sex',
            field=models.CharField(max_length=8, null=True, verbose_name='sex', choices=[(b'f', b'Female'), (b'm', b'Male')]),
        ),
    ]
