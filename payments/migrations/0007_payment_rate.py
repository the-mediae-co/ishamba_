# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0006_payment_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='rate',
            field=models.ForeignKey(to='payments.SubscriptionRate', null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
