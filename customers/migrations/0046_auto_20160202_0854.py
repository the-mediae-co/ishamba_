# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0045_auto_20160119_1126'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='heard_about_us',
            field=models.CharField(blank=True, max_length=50, verbose_name='how the customer heard about us', choices=[(b'tv', b'SSU TV'), (b'rd', b'SSU Radio'), (b'fr', b'Friend'), (b'ot', b'Other')]),
        ),
        migrations.AddField(
            model_name='customer',
            name='phone_type',
            field=models.CharField(blank=True, max_length=50, verbose_name='phone type', choices=[(b's', b'Smartphone'), (b'b', b'Basic phone'), (b'f', b'Feature phone')]),
        ),
    ]
