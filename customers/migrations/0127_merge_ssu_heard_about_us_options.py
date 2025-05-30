# Generated by Django 4.1.9 on 2024-02-19 18:12

from django.db import migrations, models

from customers.constants import HEARD_ABOUT_US


def merge_ssu_heard_about_us_options(apps, schema_editor):
    Customer = apps.get_model('customers', 'customer')
    Customer.objects.filter(
        heard_about_us__in=['tv', 'rd']
    ).update(heard_about_us=HEARD_ABOUT_US.SSU)


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0126_alter_customer_farm_size_alter_customer_join_method_and_more'),
    ]

    operations = [
        migrations.RunPython(merge_ssu_heard_about_us_options, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customer',
            name='heard_about_us',
            field=models.CharField(blank=True, choices=[('fr', 'Friend'), ('ot', 'Other'), ('ss', 'Shamba Shape Up'), ('is', 'Ishamba Web'), ('bm', 'Budget Mkononi Web')], max_length=50, verbose_name='how the customer heard about us'),
        ),
    ]
