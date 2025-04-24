# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0010_auto_20150115_1124'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='cost',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=5, blank=True),
            preserve_default=True,
        ),
    ]
