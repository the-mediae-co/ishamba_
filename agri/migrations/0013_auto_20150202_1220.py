# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0012_auto_20150202_1210'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commodity',
            name='short_name',
            field=models.CharField(unique=True, max_length=14, verbose_name='short name'),
            preserve_default=True,
        ),
    ]
