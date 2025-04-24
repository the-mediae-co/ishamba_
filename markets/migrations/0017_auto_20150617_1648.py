# -*- coding: utf-8 -*-


from django.db import models, migrations


def populate_short_name_field(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
    expects.
    """
    Market = apps.get_model('markets', 'Market')

    for m in Market.objects.all():
        m.short_name = m.name[:6]
        m.save()


def depopulate_short_name_field(apps, schema_editor):
    """ Just erase the field's values.
    """
    Market = apps.get_model('markets', 'Market')

    Market.objects.all().update(short_name='')


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0016_auto_20150617_1648'),
    ]

    operations = [
        migrations.RunPython(populate_short_name_field, depopulate_short_name_field),
        migrations.AlterField(
            model_name='market',
            name='short_name',
            field=models.CharField(unique=True, max_length=6),
            preserve_default=True,
        ),
    ]
