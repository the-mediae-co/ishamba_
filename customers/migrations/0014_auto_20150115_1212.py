# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0013_taskupdate_update_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='taskupdate',
            name='update_type',
            field=models.CharField(blank=True, max_length=50, null=True, choices=[(b'cannot-contact', b'Cannot contact customer')]),
            preserve_default=True,
        ),
    ]
