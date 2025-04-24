# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0035_auto_20150708_1011'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='commodities',
            field=models.ManyToManyField(related_name='farmers', verbose_name='commodities farmed', to='agri.Commodity'),
        ),
    ]
