# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0005_auto_20141218_1700'),
    ]

    operations = [
        migrations.AddField(
            model_name='commodity',
            name='gets_market_prices',
            field=models.BooleanField(default=False, help_text=b'Market prices are regularly received for this commodity.', verbose_name='Gets market prices'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='commodity',
            name='variant_of',
            field=models.ForeignKey(blank=True, to='agri.Commodity', help_text=b'The commodity-stream from which the customer will be sent SMS tips.', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
