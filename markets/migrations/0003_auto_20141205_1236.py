# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_auto_20141205_0943'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketprice',
            name='amount',
            field=models.PositiveSmallIntegerField(default=100, help_text=b'The number of [units] that this price is for.', max_length=30, verbose_name='amount'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='marketprice',
            name='price',
            field=models.PositiveSmallIntegerField(default=100, help_text=b'In Kenyan shillings.', verbose_name='price'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='marketprice',
            name='source',
            field=models.CharField(default='some agency', max_length=30, verbose_name='source'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='marketprice',
            name='unit',
            field=models.CharField(default='kg', max_length=30, verbose_name='unit'),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='marketprice',
            unique_together=set([('date', 'market', 'commodity', 'source')]),
        ),
    ]
