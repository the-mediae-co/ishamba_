# -*- coding: utf-8 -*-

import operator

from django.db import migrations
from django.db.models import Q
from functools import reduce


def update_null_rows(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
    expects.
    """
    fields = ('name', 'address_village', 'address_ward', 'address_county',
              'preferred_language', 'notes')
    Customer = apps.get_model("customers", "Customer")

    customers = Customer.objects.filter(
        reduce(operator.or_, [Q((f + '__isnull', True)) for f in fields]))

    for c in customers:
        updated_fields = []
        for field in fields:
            if getattr(c, field) is None:
                setattr(c, field, '')
                updated_fields.append(field)
        c.save(update_fields=updated_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0043_auto_20160118_1206'),
    ]

    operations = [
        migrations.RunPython(update_null_rows, None),
    ]
