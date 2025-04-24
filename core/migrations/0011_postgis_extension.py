# -*- coding: utf-8 -*-
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_auto_20170406_1620'),
    ]

    operations = [
        CreateExtension('postgis'),
    ]
