# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0001_initial'),
        ('customers', '0010_auto_20141216_1137'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='weather_area',
            field=models.ForeignKey(editable=False, to='weather.WeatherArea', null=True, verbose_name='weather area', on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
