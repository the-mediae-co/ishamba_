# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0014_auto_20150424_1402'),
    ]

    operations = [
        migrations.AddField(
            model_name='offer',
            name='_specific_subclass',
            field=models.CharField(default='t', max_length=200),
            preserve_default=False,
        ),
    ]
