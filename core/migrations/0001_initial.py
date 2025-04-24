# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledJob',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task', models.CharField(help_text=b'something to identify the purpose of this job, e.g. "send all weather 2015-05-22"', max_length=30)),
                ('date_started', models.DateTimeField()),
                ('date_completed', models.DateTimeField(null=True)),
                ('completed', models.BooleanField(default=False)),
                ('was_successful', models.BooleanField(default=False)),
                ('report', models.TextField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
