# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0002_auto_20141222_1804'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='cco',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='call',
            name='issue_resolved',
            field=models.CharField(max_length=100, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='call',
            name='notes',
            field=models.TextField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
