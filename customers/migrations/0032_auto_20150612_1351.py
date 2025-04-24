# -*- coding: utf-8 -*-


from django.db import models, migrations


def convert_many_to_many_to_multiple_foreign_keys(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
    expects.
    """
    Customer = apps.get_model("customers", "Customer")


    for customer in Customer.objects.all():
        markets = customer.market_subscriptions.all()
        for x in range(min(len(markets), 2)):
            setattr(customer, 'market_subscription_{}'.format(str(x+1)), markets[x])
        customer.save()


def convert_multiple_foreign_keys_to_many_to_many(apps, schema_editor):
    """ This will discard backup market choices, and also overwrite any
    existing market_subscriptions entries.
    """
    Customer = apps.get_model("customers", "Customer")
    Market = apps.get_model('markets', 'Market')

    for customer in Customer.objects.all():
        for attr in ['market_subscription_1', 'market_subscription_2']:
            market = getattr(customer, attr)
            if market:
                customer.market_subscriptions.add(market)


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0031_auto_20150611_1621'),
    ]

    operations = [
        migrations.RunPython(convert_many_to_many_to_multiple_foreign_keys, convert_multiple_foreign_keys_to_many_to_many),
    ]
