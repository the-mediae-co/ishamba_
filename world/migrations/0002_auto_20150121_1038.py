# -*- coding: utf-8 -*-


from django.db import models, migrations

import os
from django.contrib.gis.utils import LayerMapping
import world


def import_world_borders(apps, schema_editor):
    """ This is pretty much verbatim from
        https://docs.djangoproject.com/en/dev/ref/contrib/gis/tutorial/#gdal-interface
    """

    world_mapping = {
        'fips': 'FIPS',
        'iso2': 'ISO2',
        'iso3': 'ISO3',
        'un': 'UN',
        'name': 'NAME',
        'area': 'AREA',
        'pop2005': 'POP2005',
        'region': 'REGION',
        'subregion': 'SUBREGION',
        'lon': 'LON',
        'lat': 'LAT',
        'mpoly': 'MULTIPOLYGON',
    }

    # Historical version of the WorldBorder model.
    WorldBorder = apps.get_model("world", "WorldBorder")

    # open the world borders shapefile
    world_shp = os.path.abspath(os.path.join(os.path.dirname(world.__file__),
                                             'data/old/TM_WORLD_BORDERS-0.3.shp'))

    # The import function from the tutorial
    lm = LayerMapping(WorldBorder, world_shp, world_mapping,
                      transform=False, encoding='iso-8859-1')
    lm.save(strict=True, verbose=True)


def delete_all_world_borders(apps, schema_editor):
    apps.get_model("world", "WorldBorder").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('world', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(import_world_borders, delete_all_world_borders),
    ]
