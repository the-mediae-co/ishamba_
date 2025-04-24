# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0007_call_duration_in_queue'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='connected_on',
            field=models.DateTimeField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='call',
            name='hanged_on',
            field=models.DateTimeField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
