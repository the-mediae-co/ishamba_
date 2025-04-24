# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0021_commoditysubscription_ended'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(unique=True, max_length=100, verbose_name='name')),
            ],
            options={
                'verbose_name_plural': 'Customer Categories',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='customer',
            name='categories',
            field=models.ManyToManyField(to='customers.CustomerCategory', blank=True),
            preserve_default=True,
        ),
    ]
