# Generated by Django 2.2.24 on 2021-12-04 20:50

import os
import subprocess
from django.db import migrations
from django.conf import settings


def populate_border_data(apps, schema_editor):
    db = settings.DATABASES['default']
    db_name = db.get('NAME')
    db_host = db.get('HOST', None)
    db_user = db.get('USER', None)
    db_password = db.get('PASSWORD', None)
    # The world Border data resides in the public schema
    if schema_editor.connection.schema_name == 'public':
        # First clear out existing table data if it exists
        remove_border_data(apps, schema_editor)

        # Then populate the borders database
        boundaries_filename = "borders.pg_dump"
        file_path = os.path.join(os.path.dirname(__file__), "../data/", boundaries_filename)

        # Build the pg_restore command to populate the Border and BorderLevelNames tables
        # pg_restore -Fc -j 8 -v --data-only --no-owner --schema=public
        # -h basecamp.c2sjguiuzm0n.eu-west-1.rds.amazonaws.com -U basecamp -d basecamp world/data/borders.pg_dump
        if db_password:
            cmd = [f"PGPASSWORD={db_password}"]
        else:
            cmd = []
        cmd.extend(["pg_restore", "-Fc", "--jobs=8", "-v", "--data-only", "--no-owner", "--schema=public", f"--dbname={db_name}"])

        if db_host:
            cmd.append(f"-h {db_host}")

        if db_user:
            cmd.append(f"-U {db_user}")

        cmd.append(f"{file_path}")

        try:
            subprocess.run(" ".join(cmd), shell=True)
        except subprocess.CalledProcessError as e:
            print(e.returncode)
            print(e.stdout)
            print(e.stderr)
            raise e

        # Correct the old table's County names to match the new DB. This is
        # necessary to enable remapping of customers from the old county db to the new.
        with schema_editor.connection.cursor() as cursor:
            sql = f"UPDATE {schema_editor.connection.schema_name}.world_county " \
                  f"SET name = 'Tharaka Nithi' WHERE name = 'Nithi'"  # NOQA
            cursor.execute(sql, )


def remove_border_data(apps, schema_editor):
    if schema_editor.connection.schema_name == 'public':
        with schema_editor.connection.cursor() as cursor:
            sql = f"DELETE FROM {schema_editor.connection.schema_name}.world_border"  # NOQA
            cursor.execute(sql, )
            sql = f"DELETE FROM {schema_editor.connection.schema_name}.world_borderlevelname"  # NOQA
            cursor.execute(sql, )


class Migration(migrations.Migration):
    atomic = False  # Big data set repopulation, so transactions add a lot of overhead
    dependencies = [
        ('world', '0008_border_borderlevelname'),
    ]

    operations = [
        migrations.RunPython(populate_border_data, reverse_code=remove_border_data),
    ]
