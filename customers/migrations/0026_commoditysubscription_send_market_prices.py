# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0025_auto_20150508_1739'),
    ]

    operations = [
        migrations.AddField(
            model_name='commoditysubscription',
            name='send_market_prices',
            field=models.BooleanField(default=True, verbose_name='send market price updates'),
            preserve_default=True,
        ),
    ]
