# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customers', '0010_auto_20141216_1137'),
    ]

    operations = [
        migrations.CreateModel(
            name='Call',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('provided_id', models.CharField(max_length=100)),
                ('caller_number', models.CharField(max_length=100)),
                ('destination_number', models.CharField(max_length=100)),
                ('direction', models.CharField(max_length=100)),
                ('duration', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('is_active', models.BooleanField(default=False)),
                ('connected', models.BooleanField(default=False)),
                ('cost', models.PositiveSmallIntegerField()),
                ('issue_resolved', models.CharField(max_length=100)),
                ('notes', models.TextField()),
                ('cco', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL)),
                ('customer', models.ForeignKey(to='customers.Customer', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
