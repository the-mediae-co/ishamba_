# Generated by Django 3.2.13 on 2022-06-27 13:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0058_remove_smsresponsekeyword_response'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsresponsetemplate',
            name='sender',
            field=models.CharField(default='21606', help_text='The sender ID this response will be sent from.', max_length=20, verbose_name='sender'),
            preserve_default=False,
        ),
    ]
