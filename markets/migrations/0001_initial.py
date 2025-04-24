# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Market',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(max_length=160)),
                ('location', django.contrib.gis.db.models.fields.PointField(srid=4326)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MarketPrice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('date', models.DateField()),
                ('commodity', models.ForeignKey(to='agri.Commodity', on_delete=models.CASCADE)),
                ('market', models.ForeignKey(to='markets.Market', on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
