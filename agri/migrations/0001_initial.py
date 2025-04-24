# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AgriTipSMS',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('week', models.SmallIntegerField(verbose_name='week')),
                ('text', models.CharField(max_length=160, verbose_name='text')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Commodity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(unique=True, max_length=100, verbose_name='name')),
                ('commodity_type', models.CharField(default=b'crop', max_length=10, verbose_name='commodity type', choices=[(b'crop', b'Crop'), (b'livestock', b'Livestock')])),
                ('epoch_description', models.CharField(help_text=b'The event from which other dates are measured, e.g. "calf due-date". Leave blank for seasonal commodities.', max_length=255, verbose_name='epoch description')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='agritipsms',
            name='commodity',
            field=models.ForeignKey(verbose_name='commodity', to='agri.Commodity', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='agritipsms',
            name='regions',
            field=models.ManyToManyField(to='agri.Region', verbose_name='regions'),
            preserve_default=True,
        ),
    ]
