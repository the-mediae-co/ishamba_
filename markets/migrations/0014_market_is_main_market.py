# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0013_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='market',
            name='is_main_market',
            field=models.BooleanField(default=False, help_text=b'Are price updates are reliably regularly received?'),
            preserve_default=True,
        ),
    ]
