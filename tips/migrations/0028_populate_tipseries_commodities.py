# Generated by Django 4.1.7 on 2023-02-21 20:38

from django.db import migrations


def convert_data(apps, schema_editor):
    """
        Converts:
           - Searches for commodities that match the TipSeries name, setting the new commodities field.
    """
    TipSeries = apps.get_model('tips', 'TipSeries')
    Commodity = apps.get_model('agri', 'Commodity')

    for ts in TipSeries.objects.all():
        try:
            commodity = Commodity.objects.get(name__iexact=ts.name)
        except Commodity.DoesNotExist:
            continue  # If no match, don't make an assignment

        ts.commodity = commodity
        ts.save()


def reverse_data(apps, schema_editor):
    """
        Reverses:
           - No need to reverse
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tips", "0027_tipseries_commodity_and_more"),
    ]

    operations = [
        migrations.RunPython(convert_data, reverse_code=reverse_data),
    ]
