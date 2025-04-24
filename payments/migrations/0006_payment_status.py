# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_payment_extra'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(default=1, max_length=30, verbose_name='status', choices=[(b'01', b'Accepted'), (b'02', b'Account not found'), (b'03', b'Invalid payment')]),
            preserve_default=False,
        ),
    ]
