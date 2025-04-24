# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0013_merge'),
        ('customers', '0030_auto_20150608_1218'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='market_subscription_1',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, verbose_name='market subscription 1', blank=True, to='markets.Market', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='customer',
            name='market_subscription_1_backup',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, verbose_name='market subscription 1 backup', blank=True, to='markets.Market', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='customer',
            name='market_subscription_2',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, verbose_name='market subscription 2', blank=True, to='markets.Market', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='customer',
            name='market_subscription_2_backup',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, verbose_name='market subscription 2 backup', blank=True, to='markets.Market', null=True),
            preserve_default=True,
        ),
    ]
