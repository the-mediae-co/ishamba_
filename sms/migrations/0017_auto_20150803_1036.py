# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0016_smsresponsetemplate_assign_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsresponsetemplate',
            name='assign_category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, blank=True, to='customers.CustomerCategory', help_text=b'Customers will have the chosen category added. Leave blank to skip category assignment.', null=True),
            preserve_default=True,
        ),
    ]
