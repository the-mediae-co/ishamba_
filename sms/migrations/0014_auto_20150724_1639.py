# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0013_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='SMSResponseKeyword',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('keyword', models.CharField(help_text=b'This will match the whole message case-insensitively, after surrounding punctuation and whitespace has been stripped.', unique=True, max_length=160, verbose_name='keyword')),
                ('is_active', models.BooleanField(default=True, verbose_name=b'is_active')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SMSResponseTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('name', models.CharField(unique=True, max_length=255, verbose_name='name')),
                ('text', models.TextField(help_text=b'Valid placeholder values are: call_centre, shortcode, till_number, year_price, month_price. Write as {call_centre}', verbose_name='text')),
                ('create_task', models.BooleanField(default=False, help_text=b'Incoming messages will result in a task. If not set, then the response will be sent with no human involvement.', verbose_name='create task')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        # Added the null=True on 2022-06-17, to prevent a psycopg2.errors.NotNullViolation when
        # reversing the removal of this field in migration 0058_remove_smsresponsekeyword_response.py
        migrations.AddField(
            model_name='smsresponsekeyword',
            name='response',
            field=models.ForeignKey(to='sms.SMSResponseTemplate', on_delete=models.CASCADE, null=True),
            preserve_default=True,
        ),
    ]
