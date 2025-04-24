# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0008_auto_20141209_1644'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='payment',
            field=models.ForeignKey(verbose_name='payment', to='payments.Payment', null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
