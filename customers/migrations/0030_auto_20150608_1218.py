# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0029_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='has_requested_stop',
            field=models.BooleanField(default=False, verbose_name='has requested stop'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='customer',
            name='is_registered',
            field=models.BooleanField(default=False, verbose_name='is registered'),
            preserve_default=True,
        ),
    ]
