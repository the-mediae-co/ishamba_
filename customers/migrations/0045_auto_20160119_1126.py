# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0044_set_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='address_county',
            field=models.CharField(default='', max_length=100, verbose_name='county'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='address_village',
            field=models.CharField(default='', max_length=100, verbose_name='village'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='address_ward',
            field=models.CharField(default='', max_length=100, verbose_name='ward'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='name',
            field=models.CharField(default='', max_length=255, verbose_name='name'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='notes',
            field=models.TextField(default='', help_text=b'Permanent notes about this customer not related to a one-off issue.', verbose_name='notes', blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='preferred_language',
            field=models.CharField(default=b'e', max_length=100, verbose_name='preferred language', choices=[(b'e', b'English'), (b'k', b'Kiswahili')]),
        ),
    ]
