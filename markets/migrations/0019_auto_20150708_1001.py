# -*- coding: utf-8 -*-


from django.db import models, migrations

MAIN_MARKETS = ["Nairobi", "Mombasa", "Nakuru", "Kisumu", "Eldoret", "Kitale"]


def set_is_main_market_field(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
    expects.
    """
    Market = apps.get_model('markets', 'Market')

    Market.objects.filter(name__in=MAIN_MARKETS).update(is_main_market=True)


def unset_is_main_market_field(apps, schema_editor):
    """ Bluntly and ignorantly set all to false.
    """
    Market = apps.get_model('markets', 'Market')

    Market.objects.all().update(is_main_market=False)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0018_auto_20150624_1735'),
    ]

    operations = [
        migrations.RunPython(set_is_main_market_field, unset_is_main_market_field),
    ]
