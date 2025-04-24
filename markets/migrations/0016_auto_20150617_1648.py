# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0015_auto_20150612_1445'),
    ]

    operations = [
        migrations.AddField(
            model_name='market',
            name='short_name',
            field=models.CharField(max_length=6, null=True),
            preserve_default=True,
        ),
    ]
