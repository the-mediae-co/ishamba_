# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0016_auto_20150427_1544'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='offer',
            options={'ordering': ('-expiry_date',)},
        ),
    ]
