# -*- coding: utf-8 -*-


from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0003_auto_20141222_1808'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='created_on',
            field=models.DateTimeField(default=datetime.datetime(2014, 12, 23, 11, 42, 10, 102956, tzinfo=datetime.timezone.utc), auto_now_add=True),
            preserve_default=False,
        ),
    ]
