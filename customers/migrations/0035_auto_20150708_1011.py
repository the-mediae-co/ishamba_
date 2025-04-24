# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.core.exceptions import ValidationError

BACKUP_MAPPING = {
    # first choice: (back up, second choice),
    "thika": ("nairobi", "nakuru"),
    "narok": ("nairobi", "nakuru"),
    "kitui": ("nairobi", "nakuru"),
    "garissa": ("nairobi", "mombasa"),
    "machakos": ("nairobi", "nakuru"),
    "embu": ("nairobi", "nakuru"),
    "karatina": ("nairobi", "nakuru"),
    "kajiado": ("nairobi", "nakuru"),
    "loitokitok": ("nairobi", "nakuru"),
    "nyahururu": ("nakuru", "nairobi"),
    "isiolo": ("nakuru", "nairobi"),
    "marimanti": ("nakuru", "nairobi"),
    "tharaka": ("nakuru", "nairobi"),
    "imenti": ("nakuru", "nairobi"),
    "malindi": ("mombasa", "nairobi"),
    "taveta": ("mombasa", "nairobi"),
    # "mombasa": ("nairobi", "nakuru"),
    # "nairobi": ("nakuru", "eldoret"),
    # "nakuru": ("eldoret", "kisumu"),
    "kakamega": ("eldoret", "kisumu"),
    "bungoma": ("eldoret", "kisumu"),
    # "kisumu": ("kisumu", "kisii"),
    "kisii": ("kisumu", "eldoret"),
    "busia": ("kitale", "eldoret"),
    "chwele": ("kitale", "eldoret"),
    # "kitale": ("kitale", "eldoret"),
}


def assign_backup_markets(apps, schema_editor):
    """ Don't import models directly - use the versions that this migration
    expects.
    """
    Customer = apps.get_model('customers', 'Customer')
    Market = apps.get_model('markets', 'Market')

    market_subscription_attrs = ['market_subscription_1',
                                 'market_subscription_2']  # not the backups
    errors = []
    for c in Customer.objects.all():
        has_changed = False
        existing_subscribed_markets = [
            getattr(c, attr).name.lower() for attr in market_subscription_attrs
            if getattr(c, attr) is not None
        ]

        for attr in market_subscription_attrs:
            primary = getattr(c, attr)
            backup_attr = attr + '_backup'

            if primary:
                primary = Market.objects.get(id=primary.id)
            if primary and not primary.is_main_market and not getattr(c, backup_attr):
                backup_candidates = [
                    m for m in BACKUP_MAPPING[primary.name.lower()]
                    if m not in existing_subscribed_markets
                ]
                if backup_candidates:
                    chosen = backup_candidates[0]
                    setattr(c, backup_attr, Market.objects.get(name__iexact=chosen))
                    has_changed = True
                    existing_subscribed_markets.append(chosen)
        if has_changed:
            try:
                c.clean_fields(exclude=[
                    'id', 'created', 'creator_id', 'last_updated',
                    'last_editor_id', 'name', 'sex', 'phone',
                    'address_village', 'address_ward', 'address_sub_county',
                    'address_county', 'preferred_language', 'notes',
                    'location', 'region', 'weather_area', 'farm_size',
                    'has_requested_stop', 'is_registered',
                    'date_registered'])
            except ValidationError as e:
                errors.append(e)
            else:
                c.save()
    if errors:
        raise Exception(errors)


def unassign_backup_markets(apps, schema_editor):
    """ Bluntly and ignorantly set all to None.
    """
    Customer = apps.get_model('customers', 'Customer')

    Customer.objects.all().update(market_subscription_1_backup=None,
                                  market_subscription_2_backup=None)


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0034_customer_date_registered'),
        ('markets', '0019_auto_20150708_1001'),
    ]

    operations = [
        migrations.RunPython(assign_backup_markets, unassign_backup_markets),
    ]
