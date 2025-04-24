# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='agritipsms',
            options={'verbose_name': 'Agri-tip SMS'},
        ),
        migrations.AlterModelOptions(
            name='commodity',
            options={'verbose_name_plural': 'Commodities'},
        ),
        migrations.AlterField(
            model_name='commodity',
            name='epoch_description',
            field=models.CharField(help_text=b'The event from which other dates are measured, e.g. "calf due-date". Leave blank for seasonal commodities.', max_length=255, null=True, verbose_name='epoch description', blank=True),
            preserve_default=True,
        ),
    ]
