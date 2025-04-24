# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0012_auto_20150112_1647'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskupdate',
            name='update_type',
            field=models.CharField(blank=True, max_length=10, null=True, choices=[(b'cannot-contact-customer', b'Cannot contact customer')]),
            preserve_default=True,
        ),
    ]
