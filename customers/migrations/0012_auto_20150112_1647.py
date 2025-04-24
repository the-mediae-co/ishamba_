# -*- coding: utf-8 -*-


from django.db import models, migrations
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0011_customer_weather_area'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='phone',
            field=phonenumber_field.modelfields.PhoneNumberField(unique=True, max_length=128),
            preserve_default=True,
        ),
    ]
