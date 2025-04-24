# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0019_auto_20150227_1414'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='survey',
            field=models.CharField(default=b'0', max_length=30, verbose_name='baseline survey participation', choices=[(b'0', b'Not in survey'), (b'1', b'Survey participant, given free subscription'), (b'2', b'Survey participant, nothing else')]),
            preserve_default=True,
        ),
    ]
