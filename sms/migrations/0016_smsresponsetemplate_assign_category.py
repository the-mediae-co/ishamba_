# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0035_auto_20150708_1011'),
        ('sms', '0015_auto_20150803_1024'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsresponsetemplate',
            name='assign_category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, blank=True, to='customers.CustomerCategory', null=True),
            preserve_default=True,
        ),
    ]
