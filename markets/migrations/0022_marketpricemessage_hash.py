# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-07-25 16:51


from django.db import migrations, models
import markets.models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0021_auto_20160126_1612'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketpricemessage',
            name='hash',
            field=models.CharField(default=markets.models.generate_mpm_hash,
                                   max_length=32, null=True),
        ),
    ]
