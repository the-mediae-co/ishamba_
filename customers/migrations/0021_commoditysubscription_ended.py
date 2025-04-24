# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0020_customer_survey'),
    ]

    operations = [
        migrations.AddField(
            model_name='commoditysubscription',
            name='ended',
            field=models.BooleanField(default=False, help_text=b'In the case of a moveable-feast subscription, indicates that the customer has come to the end of the agri-tip stream, and is receiving tips from the fallback commodity.'),
            preserve_default=True,
        ),
    ]
