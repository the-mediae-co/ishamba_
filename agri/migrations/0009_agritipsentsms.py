# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0008_auto_20141222_1537'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgriTipSentSMS',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('text', models.CharField(max_length=160, null=True)),
                ('time_sent', models.DateTimeField(null=True)),
                ('tip', models.ForeignKey(to='agri.AgriTipSMS', on_delete=models.SET_NULL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
