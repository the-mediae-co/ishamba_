# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0002_incomingsms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incomingsms',
            name='from_num',
            field=models.CharField(max_length=30),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='text',
            field=models.CharField(max_length=500),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='to_num',
            field=models.CharField(max_length=30),
            preserve_default=True,
        ),
    ]
