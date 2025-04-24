# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0017_merge'),
    ]

    operations = [
        migrations.RenameField('agritipsms', 'week', 'number'),
        migrations.AlterField(
            model_name='agritipsms',
            name='number',
            field=models.SmallIntegerField(verbose_name='number'),
            preserve_default=True,
        ),
    ]
