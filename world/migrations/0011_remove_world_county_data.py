# Generated by Django 2.2.24 on 2021-12-12 14:22

from django.db import migrations


def remove_county_data(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        with schema_editor.connection.cursor() as cursor:
            sql = f"DELETE FROM {schema_editor.connection.schema_name}.world_county"  # NOQA
            cursor.execute(sql, )


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0104_remove_old_location_fields'),
        ('tips', '0021_remove_old_county'),
        ('weather', '0018_remove_old_county'),
        ('world', '0010_remove_worldboundary'),
    ]

    operations = [
        migrations.RunPython(remove_county_data, reverse_code=migrations.RunPython.noop),
    ]
