# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0012_auto_20150424_1246'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='offer',
            name='offer_type',
        ),
    ]
