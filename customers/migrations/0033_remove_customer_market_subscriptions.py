# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0032_auto_20150612_1351'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customer',
            name='market_subscriptions',
        ),
    ]
