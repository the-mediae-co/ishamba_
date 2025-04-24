# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('calls', '0004_call_created_on'),
    ]

    operations = [
        migrations.CreateModel(
            name='CallCenterPhone',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_active', models.BooleanField(default=True)),
                ('phone_number', models.CharField(max_length=100)),
                ('operator', models.OneToOneField(null=True, blank=True, editable=False, to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
