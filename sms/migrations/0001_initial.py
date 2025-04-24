# -*- coding: utf-8 -*-


from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('customers', '0008_auto_20141209_1644'),
    ]

    operations = [
        migrations.CreateModel(
            name='SMSRecipient',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('creator_id', models.IntegerField(null=True, blank=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('last_editor_id', models.IntegerField(null=True, blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('extra', jsonfield.fields.JSONField(null=True, blank=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType', on_delete=models.PROTECT)),
                ('recipient', models.ForeignKey(to='customers.Customer', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='smsrecipient',
            unique_together=set([('recipient', 'content_type', 'object_id')]),
        ),
    ]
