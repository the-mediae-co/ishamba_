# -*- coding: utf-8 -*-


from django.db import models, migrations
import core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0013_remove_offer_offer_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='VerifyInStoreOffer',
            fields=[
                ('offer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='payments.Offer', on_delete=models.CASCADE)),
                ('message', core.fields.SMSCharField(help_text="Must contain a string of X's to represent the code, length to match the specified code length.", max_length=160, verbose_name=b'message')),
                ('confirmation_message', core.fields.SMSCharField(help_text='Response to send to a retailer when a verify-in-store voucher is valid.', max_length=160, verbose_name=b'confirmation message', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('payments.offer',),
        ),
        migrations.RemoveField(
            model_name='redeeminstoreoffer',
            name='offer_ptr',
        ),
        migrations.DeleteModel(
            name='RedeemInStoreOffer',
        ),
    ]
