# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0010_auto_20150424_1229'),
    ]

    operations = [
        migrations.CreateModel(
            name='FreeSubscriptionOffer',
            fields=[
                ('offer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='payments.Offer', on_delete=models.CASCADE)),
                ('months', models.PositiveSmallIntegerField(help_text='How many months does this give the customer?', null=True, verbose_name='months', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('payments.offer',),
        ),
        migrations.CreateModel(
            name='RedeemInStoreOffer',
            fields=[
                ('offer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='payments.Offer', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=('payments.offer',),
        ),
        migrations.RemoveField(
            model_name='offer',
            name='confirmation_message',
        ),
        migrations.RemoveField(
            model_name='offer',
            name='message',
        ),
        migrations.RemoveField(
            model_name='offer',
            name='months_free',
        ),
    ]
