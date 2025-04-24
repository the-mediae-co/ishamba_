# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0006_auto_20141205_0943'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='address_county',
            field=models.CharField(max_length=100, null=True, verbose_name='county'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='address_sub_county',
            field=models.CharField(max_length=100, null=True, verbose_name='sub-county'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='address_village',
            field=models.CharField(max_length=100, null=True, verbose_name='village'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='address_ward',
            field=models.CharField(max_length=100, null=True, verbose_name='ward'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='name',
            field=models.CharField(max_length=255, null=True, verbose_name='name'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='preferred_language',
            field=models.CharField(default=b'e', max_length=100, null=True, verbose_name='preferred language', choices=[(b'e', b'English'), (b'k', b'Kiswahili')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='region',
            field=models.ForeignKey(verbose_name='agricultural region', to='agri.Region', null=True, on_delete=models.SET_NULL),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='customer',
            name='sex',
            field=models.CharField(default=b'f', max_length=8, null=True, verbose_name='sex', choices=[(b'f', b'Female'), (b'm', b'Male')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='taskupdate',
            name='status',
            field=models.CharField(default=b'in progress', max_length=100, verbose_name='status', choices=[(b'in progress', b'In progress'), (b'resolved', b'Resolved'), (b'unresolved', b'Unresolved')]),
            preserve_default=True,
        ),
    ]
