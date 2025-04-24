# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0003_auto_20141205_1236'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketprice',
            name='amount',
            field=models.PositiveSmallIntegerField(help_text=b'The number of [unit]s that this price is for.', max_length=30, verbose_name='amount'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='marketprice',
            name='date',
            field=models.DateField(help_text=b'The date this price was retrieved at the market.', verbose_name='date'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='marketprice',
            unique_together=set([('date', 'market', 'commodity')]),
        ),
    ]
