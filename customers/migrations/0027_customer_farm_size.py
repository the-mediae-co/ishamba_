# -*- coding: utf-8 -*-


from django.db import models, migrations
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0026_commoditysubscription_send_market_prices'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='farm_size',
            field=models.DecimalField(decimal_places=2, choices=[(Decimal('0.0'), b'0&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;0.25 acres'), (Decimal('0.25'), b'0.25&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;0.5 acres'), (Decimal('0.5'), b'0.5&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;0.75 acres'), (Decimal('0.75'), b'0.75&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;1 acres'), (Decimal('1'), b'1&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;1.5 acres'), (Decimal('1.5'), b'1.5&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;2 acres'), (Decimal('2'), b'2&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;3 acres'), (Decimal('3'), b'3&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;5 acres'), (Decimal('5'), b'5&nbsp;&lte;&nbsp;size&nbsp;&lt;&nbsp;10 acres'), (Decimal('10'), b'size&nbsp;&gte;&nbsp;10 acres')], max_digits=4, blank=True, null=True, verbose_name='size of farm'),
            preserve_default=True,
        ),
    ]
