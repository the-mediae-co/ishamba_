# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0013_auto_20150202_1220'),
    ]

    operations = [
        migrations.AddField(
            model_name='commodity',
            name='fallback_commodity',
            field=models.ForeignKey(blank=True, to='agri.Commodity', help_text=b'For date-based agri-tip streams only: the commodity that will supply tips when this stream ends.', null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commodity',
            name='variant_of',
            field=models.ForeignKey(related_name='variants', blank=True, to='agri.Commodity', help_text=b'The commodity-stream from which the customer will be sent SMS tips. Leave blank if this commodity has its own agri-tip stream.', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
