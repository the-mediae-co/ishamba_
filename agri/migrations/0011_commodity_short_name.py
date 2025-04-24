# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0010_auto_20150128_1216'),
    ]

    operations = [
        migrations.AddField(
            model_name='commodity',
            name='short_name',
            field=models.CharField(max_length=14, null=True, verbose_name='short name'),
            preserve_default=True,
        ),
    ]
