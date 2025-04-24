# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0013_pushersession_provided_call_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='call',
            name='issue_resolved',
        ),
    ]
