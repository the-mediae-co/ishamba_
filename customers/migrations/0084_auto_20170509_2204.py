# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-09 19:04


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0083_auto_20170509_1802'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerquestionanswer',
            name='text',
            field=models.CharField(max_length=255, verbose_name=b'Answer'),
        ),
    ]
