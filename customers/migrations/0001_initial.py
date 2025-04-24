# -*- coding: utf-8 -*-


from django.db import models, migrations
import phonenumber_field.modelfields
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0001_initial'),
        ('agri', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('sex', models.CharField(max_length=100, verbose_name='sex')),
                ('phone', phonenumber_field.modelfields.PhoneNumberField(max_length=128)),
                ('address_village', models.CharField(max_length=100, verbose_name='village')),
                ('address_ward', models.CharField(max_length=100, verbose_name='ward')),
                ('address_sub_county', models.CharField(max_length=100, verbose_name='sub-county')),
                ('address_county', models.CharField(max_length=100, verbose_name='county')),
                ('preferred_language', models.CharField(max_length=100, verbose_name='preferred language')),
                ('notes', models.TextField(help_text=b'Permanent notes about this customer not related to a one-off issue', verbose_name='notes')),
                ('location', django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('commodities', models.ManyToManyField(related_name='farmers', to='agri.Commodity')),
                ('market_subscriptions', models.ManyToManyField(to='markets.Market')),
                ('region', models.ForeignKey(verbose_name='agricultural region', to='agri.Region', on_delete=models.SET_NULL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
