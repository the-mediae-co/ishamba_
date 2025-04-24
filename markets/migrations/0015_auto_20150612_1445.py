# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0014_market_is_main_market'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='market',
            options={'ordering': ('name',)},
        ),
    ]
