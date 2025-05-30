# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2016-11-21 10:02


import customers.models
import datetime
from django.db import migrations, models

from core.utils.datetime import _one_year_from_today

class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0070_auto_20161107_1413'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='end_date',
            field=models.DateField(db_index=True, default=_one_year_from_today, help_text='Note that the subscription period is inclusive of the end date'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='start_date',
            field=models.DateField(db_index=True, default=datetime.date.today),
        ),
    ]
