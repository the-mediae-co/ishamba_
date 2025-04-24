# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0009_auto_20150423_1715'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offer',
            name='months_free',
            field=models.PositiveSmallIntegerField(help_text='How many months does this give the customer?', null=True, verbose_name='months free', blank=True),
            preserve_default=True,
        ),
    ]
