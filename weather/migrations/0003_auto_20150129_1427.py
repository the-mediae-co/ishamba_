# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0002_weatherforecastsentsms'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='forecastday',
            options={'ordering': ('target_date',)},
        ),
    ]
