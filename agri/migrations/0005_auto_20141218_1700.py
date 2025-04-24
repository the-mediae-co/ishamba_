# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0004_auto_20141218_1459'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='agritipsms',
            name='regions',
        ),
        migrations.AddField(
            model_name='agritipsms',
            name='region',
            field=models.ForeignKey(verbose_name='region', blank=True, to='agri.Region', null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='agritipsms',
            unique_together=set([('commodity', 'region', 'week')]),
        ),
    ]
