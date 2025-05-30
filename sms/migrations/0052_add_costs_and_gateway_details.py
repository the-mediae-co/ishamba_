# Generated by Django 3.2.11 on 2022-02-14 14:06

from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0051_django_32_field_changes'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyoutgoingsmssummary',
            name='cost',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10),
        ),
        migrations.AddField(
            model_name='dailyoutgoingsmssummary',
            name='cost_units',
            field=models.CharField(default='?', max_length=8),
        ),
        migrations.AddField(
            model_name='dailyoutgoingsmssummary',
            name='country',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='world.border'),
        ),
        migrations.AddField(
            model_name='dailyoutgoingsmssummary',
            name='gateway_name',
            field=models.CharField(default='?', max_length=120),
        ),
        migrations.AddField(
            model_name='smsrecipient',
            name='cost',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=6),
        ),
        migrations.AddField(
            model_name='smsrecipient',
            name='cost_units',
            field=models.CharField(default='?', max_length=8),
        ),
        migrations.AddField(
            model_name='smsrecipient',
            name='gateway_name',
            field=models.CharField(default='?', max_length=120),
        ),
        migrations.AddIndex(
            model_name='dailyoutgoingsmssummary',
            index=models.Index(fields=['gateway_name'], name='gateway_name_idx'),
        ),
        migrations.RemoveConstraint(
            model_name='dailyoutgoingsmssummary',
            name='unique_date_message_type',
        ),
        migrations.AddConstraint(
            model_name='dailyoutgoingsmssummary',
            constraint=models.UniqueConstraint(fields=('country', 'date', 'gateway_name', 'message_type'),
                                               name='unique_country_date_gateway_message_type'),
        ),
    ]
