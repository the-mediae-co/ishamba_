# Generated by Django 2.2.7 on 2019-11-26 10:19

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calls', '0015_call_issue_resolved'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='cco',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='CCO'),
        ),
    ]
