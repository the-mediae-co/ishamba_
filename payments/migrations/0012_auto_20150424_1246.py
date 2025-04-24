# -*- coding: utf-8 -*-


from django.db import models, migrations
import core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0011_auto_20150424_1246'),
    ]

    operations = [
        migrations.AddField(
            model_name='redeeminstoreoffer',
            name='confirmation_message',
            field=core.fields.SMSCharField(default='', help_text='Response to send to a retailer when a redeem-in-store voucher is valid.', max_length=160, verbose_name=b'confirmation message', blank=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='redeeminstoreoffer',
            name='message',
            field=core.fields.SMSCharField(default='XXXXXX', help_text="Must contain a string of X's to represent the code, length to match the specified code length.", max_length=160, verbose_name=b'message'),
            preserve_default=False,
        ),
    ]
