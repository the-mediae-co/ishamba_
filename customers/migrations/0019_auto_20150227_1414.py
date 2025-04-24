# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0018_auto_20150211_1004'),
    ]

    operations = [
        migrations.AlterField(
            model_name='taskupdate',
            name='message',
            field=models.TextField(help_text=b'Markdown formatting is supported.', null=True, verbose_name='message', blank=True),
            preserve_default=True,
        ),
    ]
