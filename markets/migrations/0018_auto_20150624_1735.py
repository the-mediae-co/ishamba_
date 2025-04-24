# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0007_auto_20150624_1735'),
        ('markets', '0017_auto_20150617_1648'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketPriceMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('text', models.CharField(max_length=160)),
                ('date', models.DateField()),
                ('prices', models.ManyToManyField(to='markets.MarketPrice')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
