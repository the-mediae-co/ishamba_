# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0001_initial'),
        ('customers', '0002_commoditysubscription_subscription'),
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='payment',
            field=models.ForeignKey(verbose_name='payment', to='payments.Payment', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='commoditysubscription',
            name='commodity',
            field=models.ForeignKey(verbose_name='commodity', to='agri.Commodity', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='commoditysubscription',
            name='subscriber',
            field=models.ForeignKey(verbose_name='subscriber', to='customers.Customer', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='customer',
            name='commodity_subscriptions',
            field=models.ManyToManyField(related_name='subscribers', through='customers.CommoditySubscription', to='agri.Commodity'),
            preserve_default=True,
        ),
    ]
