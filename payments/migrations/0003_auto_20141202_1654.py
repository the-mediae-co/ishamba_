# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_auto_20141202_1614'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='amount',
            field=models.PositiveIntegerField(help_text=b'In Kenyan shillings.', verbose_name='amount'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='payment',
            name='payment_processor',
            field=models.CharField(help_text=b'The 3rd party API that processed this payment.', max_length=30, verbose_name='payment processor'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='payment',
            name='payment_timestamp',
            field=models.DateTimeField(help_text=b'The timestamp provided by the payment processor.', verbose_name='payment timestamp'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='payment',
            name='transaction_id',
            field=models.CharField(max_length=100, verbose_name='transaction ID'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='subscriptionperiod',
            name='start_date',
            field=models.DateField(unique=True, verbose_name='start date'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='subscriptionrate',
            name='amount',
            field=models.PositiveIntegerField(help_text=b'In Kenyan shillings.', verbose_name='amount'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='subscriptionrate',
            name='months',
            field=models.PositiveIntegerField(verbose_name='months'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='subscriptionrate',
            unique_together=set([('subscription_period', 'amount')]),
        ),
    ]
