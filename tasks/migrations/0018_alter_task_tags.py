# Generated by Django 3.2.16 on 2022-12-11 13:30

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0005_auto_20220424_2025'),
        ('tasks', '0017_outgoingsms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='tags',
            field=taggit.managers.TaggableManager(blank=True, help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
    ]
