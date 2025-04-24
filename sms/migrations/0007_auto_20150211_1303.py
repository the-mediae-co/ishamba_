# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0006_bespokesentsms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incomingsms',
            name='customer',
            field=models.ForeignKey(help_text="The customer who had the SMS's 'from' number at the time the SMS was received. Customer's current number may differ from this entry's 'from' number.", to='customers.Customer', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='provided_id',
            field=models.CharField(help_text='The ID assigned by the external telecoms service.', max_length=100, verbose_name='Provided ID'),
            preserve_default=True,
        ),
    ]
