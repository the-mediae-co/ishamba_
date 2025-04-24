# -*- coding: utf-8 -*-


from django.db import models, migrations

def populate_short_name_field(apps, schema_editor):
    Commodity = apps.get_model('agri', 'Commodity')
    for commodity in Commodity.objects.all():
        commodity.short_name = commodity.name[:14]
        commodity.save()


def reverse():
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0011_commodity_short_name'),
    ]

    operations = [
        migrations.RunPython(populate_short_name_field, reverse)
    ]
