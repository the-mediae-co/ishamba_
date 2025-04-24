# -*- coding: utf-8 -*-


from django.db import models, migrations
import payments.models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0008_auto_20150423_1715'),
    ]

    operations = [
        migrations.AlterField(
            model_name='voucher',
            name='code',
            field=models.CharField(default=payments.models.generate_nonce, max_length=100, verbose_name='code'),
            preserve_default=True,
        ),
    ]
