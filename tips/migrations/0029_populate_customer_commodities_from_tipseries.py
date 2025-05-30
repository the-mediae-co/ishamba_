# Generated by Django 4.1.7 on 2023-02-21 20:38
import humanize
from django.db import migrations


def slow_convert_data(apps, schema_editor):
    """
        Converts:
           - Searches for commodities that match the TipSeries name, setting the new commodities field.
    """
    Commodity = apps.get_model('agri', 'Commodity')
    Customer = apps.get_model('customers', 'Customer')
    TipSeries = apps.get_model('tips', 'TipSeries')
    TipSeriesSubscription = apps.get_model('tips', 'TipSeriesSubscription')

    # Cache a mapping from each tipseries to it's commodity to reduce db thrashing
    ts_commodity_map = {}
    for ts_pk, ts_commodity_pk in TipSeries.objects.values_list('pk', 'commodity__pk'):
        ts_commodity_map[ts_pk] = ts_commodity_pk

    counter = 0
    customer_cache = {}
    print(f'Total subscriptions: {humanize.intcomma(TipSeriesSubscription.objects.count())}')
    for tss_customer_id, tss_series_id in TipSeriesSubscription.objects.values_list('customer_id', 'series_id'):
        counter += 1
        if counter % 50000 == 0:
            print(f'Converted: {humanize.intcomma(counter)}')

        if tss_customer_id in customer_cache.keys():
            customer = customer_cache[tss_customer_id]
        else:
            try:
                customer = Customer.objects.get(id=tss_customer_id)
                customer_cache[customer.id] = customer
            except Customer.DoesNotExist:
                continue  # If no match, don't make an assignment

        tss_commodity_id = ts_commodity_map[tss_series_id]
        # Adding the commodity if it already exists does NOT create a duplicate,
        # and is more efficient than checking.
        if tss_commodity_id is not None:
            customer.commodities.add(tss_commodity_id)

    print(f"Finished. Total: {counter}")


def convert_data(apps, schema_editor):
    """
        Converts:
           - Searches for commodities that match the TipSeries name, setting the new commodities field.
    """
    Commodity = apps.get_model('agri', 'Commodity')
    Customer = apps.get_model('customers', 'Customer')
    TipSeries = apps.get_model('tips', 'TipSeries')
    TipSeriesSubscription = apps.get_model('tips', 'TipSeriesSubscription')

    # Cache a mapping from each tipseries to it's commodity to reduce db thrashing
    ts_commodity_map = {}
    for ts_id, ts_commodity_id in TipSeries.objects.values_list('id', 'commodity__id'):
        if ts_commodity_id is not None:
            ts_commodity_map[ts_id] = ts_commodity_id

    counter = 0
    print(f'Total customers: {humanize.intcomma(Customer.objects.exclude(tip_subscriptions=None).count())}')
    for customer in Customer.objects.exclude(tip_subscriptions=None).iterator(chunk_size=10000):
        counter += 1
        if counter % 50000 == 0:
            print(f'Converted: {humanize.intcomma(counter)}')

        series_ids = set(customer.tip_subscriptions.values_list('series_id', flat=True))

        for series_id in series_ids:
            if series_id in ts_commodity_map:
                commodity_id = ts_commodity_map[series_id]
                customer.commodities.add(commodity_id)

    print(f"Finished. Total: {counter}")


def reverse_data(apps, schema_editor):
    """
        Reverses:
           - No need to reverse
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tips", "0028_populate_tipseries_commodities"),
    ]

    operations = [
        migrations.RunPython(convert_data, reverse_code=reverse_data),
    ]
