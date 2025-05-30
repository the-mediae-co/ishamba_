# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2017-03-31 11:01

from datetime import date, datetime, time, timezone

from django.db import migrations
from django.utils.timezone import make_aware


def create_new_tip_subscriptions(apps, schema_editor):
    TipSeries = apps.get_model('tips', 'TipSeries')
    TipSeriesSubscription = apps.get_model('tips', 'TipSeriesSubscription')
    CommoditySubscription = apps.get_model('customers', 'CommoditySubscription')

    all_series = TipSeries.objects.only('pk', 'name').all()
    series_dict = {s.name: s.pk for s in all_series}

    # Find all subscriptions created after the last tip subscription migration ran
    subscriptions = (CommoditySubscription.objects.exclude(ended=True)
                                                  .filter(send_agri_tips=True)
                                                  .filter(created__gte=datetime(2017, 3, 21, 14, 0, tzinfo=timezone.utc))
                                                  .only('commodity__name', 'commodity__variant_of__name', 'created', 'epoch_date', 'subscriber_id'))

    for sub in subscriptions.iterator():
        try:
            if sub.commodity.variant_of:
                series_id = series_dict[sub.commodity.variant_of.name]
            else:
                series_id = series_dict[sub.commodity.name]
        except KeyError:
            continue
        unaware_start = datetime.combine(sub.epoch_date or date(sub.created.year, 1, 1), time.min)
        aware_start = make_aware(unaware_start, timezone.utc)
        (TipSeriesSubscription.objects.create(customer_id=sub.subscriber_id,
                                              series_id=series_id,
                                              start=aware_start))


class Migration(migrations.Migration):

    dependencies = [
        ('tips', '0014_remove_send_tips_false_subs'),
    ]

    operations = [
        migrations.RunPython(create_new_tip_subscriptions, migrations.RunPython.noop)
    ]
