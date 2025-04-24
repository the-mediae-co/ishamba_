# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('calls', '0005_callcenterphone'),
    ]

    operations = [
        migrations.CreateModel(
            name='PusherSession',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('pusher_session_key', models.CharField(max_length=50)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('finished_on', models.DateTimeField(null=True, blank=True)),
                ('call_center_phone', models.ForeignKey(to='calls.CallCenterPhone', on_delete=models.CASCADE)),
                ('operator', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='callcenterphone',
            name='operator',
        ),
        migrations.AddField(
            model_name='callcenterphone',
            name='operators',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, through='calls.PusherSession', blank=True),
            preserve_default=True,
        ),
    ]
