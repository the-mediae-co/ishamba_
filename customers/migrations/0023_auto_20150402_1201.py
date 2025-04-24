# -*- coding: utf-8 -*-


from django.db import models, migrations

# We need SURVEY_CHOICES here, as the models may have changed in the working
# tree
BLANK = '0'
IN_FREE = '1'
IN_NO_FREE = '2'
SURVEY_CHOICES = (
    (BLANK, 'Not in survey'),
    (IN_FREE, 'Survey participant, given free subscription'),
    (IN_NO_FREE, 'Survey participant, nothing else'),
)


def convert_choices_to_categories(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
        expects.
    """
    Customer = apps.get_model("customers", "Customer")
    CustomerCategory = apps.get_model("customers", "CustomerCategory")

    cat_dict = {}
    for value, description in SURVEY_CHOICES:
        category, created = CustomerCategory.objects.get_or_create(name=description)
        cat_dict[value] = category

    for customer in Customer.objects.all():
        customer.categories.add(cat_dict[customer.survey])


def reverse_convert_choices_to_categories(apps, schema_editor):
    """ Attempt to keep data if it's compatible with the SURVEY_CHOICES tuple.
    """
    Customer = apps.get_model("customers", "Customer")
    CustomerCategory = apps.get_model("customers", "CustomerCategory")

    cat_dict = {}
    for value, description in SURVEY_CHOICES:
        cat_dict[description] = value

    for customer in Customer.objects.all():
        try:
            target_category = customer.categories.get(name__in=cat_dict.keys())
        except (CustomerCategory.DoesNotExist, CustomerCategory.MultipleObjectsReturned):
            pass
        else:
            customer.survey = cat_dict[target_category.name]
            customer.save()


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0022_auto_20150402_1201'),
    ]

    operations = [
        migrations.RunPython(convert_choices_to_categories, reverse_convert_choices_to_categories),
    ]
