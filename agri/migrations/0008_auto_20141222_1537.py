# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0007_auto_20141219_1721'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commodity',
            name='variant_of',
            field=models.ForeignKey(related_name='variants', blank=True, to='agri.Commodity', help_text=b'The commodity-stream from which the customer will be sent SMS tips.', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
