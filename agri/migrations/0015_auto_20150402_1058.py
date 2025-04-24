# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agri', '0014_auto_20150330_1135'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commodity',
            name='fallback_commodity',
            field=models.ForeignKey(blank=True, to='agri.Commodity', help_text=b'For event-based agri-tip streams only: the commodity that will supply tips when this stream ends.', null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
