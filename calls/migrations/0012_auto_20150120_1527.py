# -*- coding: utf-8 -*-


from django.db import models, migrations
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0011_auto_20150115_1421'),
    ]

    operations = [
        migrations.AlterField(
            model_name='callcenterphone',
            name='phone_number',
            field=phonenumber_field.modelfields.PhoneNumberField(unique=True, max_length=128),
            preserve_default=True,
        ),
    ]
