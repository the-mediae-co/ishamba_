# Generated by Django 3.2.15 on 2022-09-28 11:43

import customers.models
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0113_remove_phone_and_africas_talking_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='owns_farm',
            field=models.BooleanField(blank=True, null=True, verbose_name='owns farm'),
        ),
        migrations.CreateModel(
            name='CustomerLetItRainData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(blank=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(blank=True, null=True)),
                ('season', models.CharField(choices=[(None, 'Unknown'), ('2022s2', '2022-2nd season'), ('2023s1', '2023-1st season')], default=customers.models.get_current_farming_season, max_length=6, verbose_name='season')),
                ('data_source', models.CharField(choices=[(None, 'Unknown'), ('ussd', 'USSD'), ('web', 'Web')], default='ussd', max_length=8, verbose_name='data source')),
                ('guesses', django.contrib.postgres.fields.ArrayField(base_field=models.DateField(), blank=True, null=True, size=None)),
                ('crops_have_failed', models.BooleanField(blank=True, null=True, verbose_name='has had crops fail')),
                ('has_crop_insurance', models.BooleanField(blank=True, null=True, verbose_name='has crop insurance')),
                ('receives_weather_forecasts', models.BooleanField(blank=True, null=True, verbose_name='receives weather forecasts')),
                ('weather_source', models.CharField(blank=True, choices=[(None, 'Unknown'), ('ishamba', 'iShamba'), ('ssu', 'Shamba Shape Up'), ('other', 'Other')], max_length=20, verbose_name='weather source')),
                ('forcast_frequency_days', models.IntegerField(blank=True, null=True)),
                ('uses_certified_seed', models.BooleanField(blank=True, null=True)),
                ('fertilizer_type', models.CharField(blank=True, choices=[(None, 'Unknown'), ('organic', 'Organic'), ('synthetic', 'Synthetic'), ('both', 'both')], max_length=12, verbose_name='fertilizer type')),
                ('has_experienced_floods', models.BooleanField(blank=True, null=True)),
                ('has_experienced_droughts', models.BooleanField(blank=True, null=True)),
                ('has_experienced_pests', models.BooleanField(blank=True, null=True)),
                ('has_experienced_diseases', models.BooleanField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='letitrain_data', to='customers.customer')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
