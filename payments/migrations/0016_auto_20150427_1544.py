# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0015_offer__specific_subclass'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='voucher',
            options={'ordering': ('offer', 'number')},
        ),
    ]
