# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0014_remove_call_issue_resolved'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='issue_resolved',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
