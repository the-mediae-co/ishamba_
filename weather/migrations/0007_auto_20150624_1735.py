# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0006_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeatherForecast',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('text', models.CharField(max_length=160)),
                ('weather_area', models.ForeignKey(to='weather.WeatherArea', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='weatherforecast',
            unique_together=set([('start_date', 'weather_area')]),
        ),
    ]
