# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0033_remove_customer_market_subscriptions'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='date_registered',
            field=models.DateField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
