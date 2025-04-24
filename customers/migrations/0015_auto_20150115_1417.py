# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0014_auto_20150115_1212'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='payment',
            field=models.ForeignKey(verbose_name='payment', blank=True, to='payments.Payment', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
