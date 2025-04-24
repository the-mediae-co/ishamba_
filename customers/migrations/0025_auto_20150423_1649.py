# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0024_remove_customer_survey'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customercategory',
            options={'verbose_name_plural': 'Customer categories'},
        ),
    ]
