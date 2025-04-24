# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0009_auto_20141217_1133'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketprice',
            name='amount',
            field=models.PositiveSmallIntegerField(help_text=b'The number of [unit]s that this price is for.', verbose_name='amount'),
            preserve_default=True,
        ),
    ]
