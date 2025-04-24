# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0009_auto_20150227_1449'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bespokesentsms',
            options={'ordering': ('-time_sent',)},
        ),
    ]
