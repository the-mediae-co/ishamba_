# -*- coding: utf-8 -*-


from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_auto_20150206_1211'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='extra',
            field=jsonfield.fields.JSONField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
