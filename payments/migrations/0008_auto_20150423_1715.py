# -*- coding: utf-8 -*-


from django.db import models, migrations
import core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0025_auto_20150423_1649'),
        ('payments', '0007_payment_rate'),
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(unique=True, max_length=100, verbose_name='name')),
                ('expiry_date', models.DateField(help_text='The offer will be valid up to the end of this date in the local timezone.', verbose_name='expiry date')),
                ('months_free', models.PositiveSmallIntegerField(help_text='How many months does this give the customer?', verbose_name='months free')),
                ('offer_type', models.PositiveSmallIntegerField(choices=[(1, b'Free months'), (2, b'Verify in store')])),
                ('message', core.fields.SMSCharField(help_text="Must contain a string of X's to represent the code, length to match the specified code length.", max_length=160, verbose_name=b'message')),
                ('confirmation_message', core.fields.SMSCharField(help_text='Response to send to a retailer when a redeem-in-store voucher is valid.', max_length=160, verbose_name=b'confirmation message', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('number', models.PositiveSmallIntegerField(verbose_name='number')),
                ('code', models.CharField(max_length=100, verbose_name='code')),
                ('offer', models.ForeignKey(related_name='vouchers', to='payments.Offer', on_delete=models.CASCADE)),
                ('used_by', models.ForeignKey(related_name='used_vouchers', blank=True, to='customers.Customer', null=True, on_delete=models.SET_NULL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='voucher',
            unique_together=set([('offer', 'code'), ('offer', 'number')]),
        ),
    ]
