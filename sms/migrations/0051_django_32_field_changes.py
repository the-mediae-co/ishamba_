# Generated by Django 3.2.10 on 2021-12-31 16:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0050_populate_dailyoutgoingsmssummary'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailyoutgoingsmssummary',
            name='extra',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='outgoingsms',
            name='extra',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='smsrecipient',
            name='extra',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
