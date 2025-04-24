# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0004_auto_20141205_1556'),
    ]

    operations = [
        migrations.AlterField(
            model_name='market',
            name='name',
            field=models.CharField(unique=True, max_length=160),
            preserve_default=True,
        ),
    ]
