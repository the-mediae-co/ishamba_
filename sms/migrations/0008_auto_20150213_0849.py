# -*- coding: utf-8 -*-


from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_payment_extra'),
        ('sms', '0007_auto_20150211_1303'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsrecipient',
            name='extra',
            field=jsonfield.fields.JSONField(default={}, blank=True),
            preserve_default=True,
        ),
    ]
