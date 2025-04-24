# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0040_auto_20150904_1505'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='status',
            field=models.CharField(default=b'new', max_length=100, verbose_name='status', choices=[(b'in progress', b'In progress'), (b'resolved', b'Resolved'), (b'unresolved', b'Unresolved')]),
        ),
    ]
