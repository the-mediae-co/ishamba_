# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0009_auto_20150114_1206'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='cco',
            field=models.ForeignKey(verbose_name=b'CCO', blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
