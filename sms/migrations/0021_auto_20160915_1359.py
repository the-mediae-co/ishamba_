# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-09-15 12:59


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0020_auto_20160914_1544'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='smsrecipient',
            unique_together=set([]),
        ),
    ]
