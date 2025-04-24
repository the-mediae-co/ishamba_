# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='payment_processor',
            field=models.CharField(default='kopo kopo', max_length=30),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='payment',
            unique_together=set([('payment_processor', 'transaction_id')]),
        ),
    ]
