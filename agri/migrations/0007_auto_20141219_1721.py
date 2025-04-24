# -*- coding: utf-8 -*-


from django.db import models, migrations


CROPS = (
    # NAFIS list
    ('Dry Maize',               'Maize',            True),
    ('Green Maize',             'Maize',            True),
    ('Finger Millet',           'Millet',           True),
    ('Sorghum',                 'Sorghum',          True),
    ('Wheat',                   'Wheat',            True),
    ('Beans Canadian',          'Beans',            True),
    ('Beans Rosecoco',          'Beans',            True),
    ('Beans Mwitemania',        'Beans',            True),
    ('Mwezi Moja',              'Beans',            True),
    ('Dolichos (Njahi)',        'Beans',            True),
    ('Green Gram',              None,               True),
    ('Cowpeas',                 None,               True),
    ('Fresh Peas',              'Garden Peas',      True),
    ('Groundnuts',              None,               True),
    ('Red Irish Potatoes',      'Irish Potatoes',   True),
    ('White Irish Potatoes',    'Irish Potatoes',   True),
    ('Cassava Fresh',           'Cassava',          True),
    ('Sweet Potatoes',          None,               True),
    ('Cabbages',                None,               True),
    ('Cooking Bananas',         'Bananas',          True),
    ('Ripe Bananas',            'Bananas',          True),
    ('Carrots',                 None,               True),
    ('Tomatoes',                None,               True),
    ('Onions Dry',              'Onions',           True),
    ('Spring Onions',           None,               True),
    ('Chillies',                'Capsicums',        True),
    ('Cucumber',                None,               True),
    ('Capsicums',               None,               True),
    ('Brinjals',                None,               True),
    ('Cauliflower',             None,               True),
    ('Lettuce',                 None,               True),
    ('Passion Fruits',          None,               True),
    ('Oranges',                 None,               True),
    ('Lemons',                  None,               True),
    ('Mangoes Local',           'Mangoes',          True),
    ('Mangoes Ngowe',           'Mangoes',          True),
    ('Limes',                   None,               True),
    ('Pineapples',              None,               True),
    ('Pawpaw',                  None,               True),
    ('Avocado',                 None,               True),
    ('Kales',                   None,               True),
    ('Eggs',                    None,               True),
)


def create_crops(apps, schema_editor):
    """ Don't import Commodity directly - use the version that this
        migration expects.
    """
    pass


def reverse_create_crops(apps, schema_editor):
    """ The above is idempotent. Be lazy here.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0006_auto_20141219_1721'),
    ]

    operations = [
        migrations.RunPython(create_crops, reverse_create_crops)
    ]
