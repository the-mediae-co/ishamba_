# Generated by Django 2.2.7 on 2019-11-26 10:19

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0034_auto_20190426_1316'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bespokesentsms',
            name='sent_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='incomingsms',
            name='gateway',
            field=models.PositiveSmallIntegerField(choices=[(1, 'TrueAfrican'), (0, 'AfricasTalking'), (2, 'Digifarm')], verbose_name='Gateway'),
        ),
        migrations.AlterField(
            model_name='smsrecipient',
            name='message_status',
            field=models.CharField(db_index=True, default='Pending', max_length=50),
        ),
        migrations.AlterField(
            model_name='smsresponsekeyword',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='is_active'),
        ),
        migrations.AlterField(
            model_name='smsresponsekeyword',
            name='keyword',
            field=models.CharField(help_text='This will match the whole message case-insensitively, after surrounding punctuation and whitespace has been stripped.', max_length=160, unique=True, verbose_name='keyword'),
        ),
        migrations.AlterField(
            model_name='smsresponsetemplate',
            name='assign_category',
            field=models.ForeignKey(blank=True, help_text='Customers will have the chosen category added. Leave blank to skip category assignment.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='customers.CustomerCategory'),
        ),
        migrations.AlterField(
            model_name='smsresponsetemplate',
            name='text',
            field=models.TextField(help_text='Valid placeholder values are: call_centre, shortcode, till_number, year_price, month_price. Write as {call_centre}', verbose_name='text'),
        ),
    ]
