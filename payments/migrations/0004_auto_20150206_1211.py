# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_auto_20141202_1654'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='subscriptionrate',
            options={'ordering': ('-subscription_period__start_date', 'amount')},
        ),
    ]
