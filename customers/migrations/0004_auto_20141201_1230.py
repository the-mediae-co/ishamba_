# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0003_auto_20141128_1730'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='commodities',
            field=models.ManyToManyField(related_name='farmers', null=True, verbose_name='commodities farmed', to='agri.Commodity'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='commodity_subscriptions',
            field=models.ManyToManyField(related_name='subscribers', to='agri.Commodity', through='customers.CommoditySubscription', blank=True, help_text=b'Max. 2', verbose_name='commodity subscriptions'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='market_subscriptions',
            field=models.ManyToManyField(help_text=b'Max. 2', to='markets.Market', verbose_name='market subscriptions', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='notes',
            field=models.TextField(help_text=b'Permanent notes about this customer not related to a one-off issue.', null=True, verbose_name='notes', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='preferred_language',
            field=models.CharField(default=b'e', max_length=100, verbose_name='preferred language', choices=[(b'e', b'English'), (b'k', b'Kiswahili')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='sex',
            field=models.CharField(default=b'f', max_length=8, verbose_name='sex', choices=[(b'f', b'Female'), (b'm', b'Male')]),
            preserve_default=True,
        ),
    ]
