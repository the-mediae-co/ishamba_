# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0017_auto_20150128_1216'),
        ('sms', '0003_auto_20150109_0659'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='incomingsms',
            options={'ordering': ('received',)},
        ),
        migrations.AddField(
            model_name='incomingsms',
            name='customer',
            field=models.ForeignKey(default=1, to='customers.Customer', help_text="The customer who had the SMS's 'from' number at the time the SMS was received.", on_delete=models.CASCADE),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='incomingsms',
            name='customer_created',
            field=models.BooleanField(default=False, help_text='This was the first contact with the customer, and caused the initial creation of the customer record.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='incomingsms',
            name='provided_id',
            field=models.CharField(default=1, help_text='The ID assigned by the external telecoms service.', max_length=30, verbose_name='Provided ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='from_num',
            field=models.CharField(max_length=30, verbose_name='from'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='received',
            field=models.DateTimeField(help_text='The time the SMS was received at the telecoms service.', verbose_name='Received'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='text',
            field=models.TextField(max_length=500, verbose_name=b'text'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='to_num',
            field=models.CharField(max_length=30, verbose_name=b'to'),
            preserve_default=True,
        ),
    ]
