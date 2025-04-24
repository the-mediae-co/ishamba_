# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0023_auto_20150402_1201'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customer',
            name='survey',
        ),
    ]
