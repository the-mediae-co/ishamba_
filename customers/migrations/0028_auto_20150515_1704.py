# -*- coding: utf-8 -*-


from django.db import models, migrations
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0027_customer_farm_size'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='farm_size',
            field=models.DecimalField(decimal_places=2, choices=[(Decimal('0.0'), b'x&nbsp;&lt;&nbsp;0.25'), (Decimal('0.25'), b'0.25&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;0.5'), (Decimal('0.5'), b'0.5&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;0.75'), (Decimal('0.75'), b'0.75&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;1'), (Decimal('1'), b'1&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;1.5'), (Decimal('1.5'), b'1.5&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;2'), (Decimal('2'), b'2&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;3'), (Decimal('3'), b'3&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;5'), (Decimal('5'), b'5&nbsp;&le;&nbsp;x&nbsp;&lt;&nbsp;10'), (Decimal('10'), b'x&nbsp;&ge;&nbsp;10')], max_digits=4, blank=True, null=True, verbose_name='size of farm (acres)'),
            preserve_default=True,
        ),
    ]
