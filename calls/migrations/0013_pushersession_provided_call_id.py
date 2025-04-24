# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0012_auto_20150120_1527'),
    ]

    operations = [
        migrations.AddField(
            model_name='pushersession',
            name='provided_call_id',
            field=models.CharField(max_length=100, null=True),
            preserve_default=True,
        ),
    ]
