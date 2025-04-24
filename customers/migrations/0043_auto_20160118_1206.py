# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0042_auto_20151218_1223'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(default=b'new', max_length=100, verbose_name='status', choices=[(b'new', b'New'), (b'in progress', b'In progress'), (b'resolved', b'Resolved'), (b'unresolved', b'Unresolved')]),
        ),
        migrations.AlterField(
            model_name='taskupdate',
            name='message',
            field=models.TextField(default='', help_text=b'Markdown formatting is supported.', verbose_name='message', blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='taskupdate',
            name='status',
            field=models.CharField(max_length=100, verbose_name='status', choices=[(b'new', b'New'), (b'in progress', b'In progress'), (b'resolved', b'Resolved'), (b'unresolved', b'Unresolved')]),
        ),
    ]
