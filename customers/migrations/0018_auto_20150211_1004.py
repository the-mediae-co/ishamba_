# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0017_auto_20150128_1216'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='payment',
            field=models.OneToOneField(related_name='_subscription', null=True, blank=True, to='payments.Payment', verbose_name='payment', on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
