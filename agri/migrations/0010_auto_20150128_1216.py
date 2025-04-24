# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0009_agritipsentsms'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='commodity',
            options={'ordering': ('name',), 'verbose_name_plural': 'Commodities'},
        ),
    ]
