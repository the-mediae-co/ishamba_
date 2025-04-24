# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0014_auto_20150724_1639'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bespokesentsms',
            options={'verbose_name': 'bespoke sent SMS'},
        ),
        migrations.AlterModelOptions(
            name='incomingsms',
            options={'ordering': ('received',), 'verbose_name': 'incoming SMS'},
        ),
        migrations.AlterModelOptions(
            name='smsrecipient',
            options={'verbose_name': 'SMS recipient'},
        ),
        migrations.AlterModelOptions(
            name='smsresponsekeyword',
            options={'verbose_name': 'SMS response keyword'},
        ),
        migrations.AlterModelOptions(
            name='smsresponsetemplate',
            options={'verbose_name': 'SMS response template'},
        ),
    ]
