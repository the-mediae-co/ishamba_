# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.contrib.gis.geos import Point


MARKETS = {
    # geocoded from OSM/Nominatim
    'Eldoret': {
        'lat': 0.5198329,
        'lon': 35.2715481
    },
    'Embu': {
        'lat': -0.53596255,
        'lon': 37.6653019690204
    },
    'Kisumu': {
        'lat': -0.1971259,
        'lon': 34.7778573178751
    },
    'Nakuru': {
        'lat': -0.4598212,
        'lon': 36.10067977858
    },
    'Mombasa': {
        'lat': -4.0390145,
        'lon': 39.648390961857
    },
    'Nairobi': {
        'lat': -1.2832533,
        'lon': 36.8172449
    },
}

def update_markets(apps, schema_editor):
    """ Don't import Market directly - use the version that this migration
        expects.
    """
    pass


def reverse_update_markets(apps, schema_editor):
    """ The above is idempotent. Be lazy here.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0008_auto_20141216_1203'),
    ]

    operations = [
        migrations.RunPython(update_markets, reverse_update_markets),
    ]
