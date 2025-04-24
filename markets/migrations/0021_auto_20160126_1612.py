# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0020_auto_20150904_1425'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketpricemessage',
            name='text',
            field=models.TextField(),
        ),
    ]
