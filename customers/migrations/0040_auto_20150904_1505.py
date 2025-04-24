# -*- coding: utf-8 -*-


from django.db import models, migrations


def denullify_text_field(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    for cust in Customer.objects.filter(sex=None):
        cust.sex = ""
        cust.save()


def do_nothing(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0039_merge'),
    ]

    operations = [
        migrations.RunPython(denullify_text_field, do_nothing),
        migrations.AlterField(
            model_name='customer',
            name='sex',
            field=models.CharField(blank=True, max_length=8, verbose_name='sex', choices=[(b'f', b'Female'), (b'm', b'Male')]),
        ),
    ]
