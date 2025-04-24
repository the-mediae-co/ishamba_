from actstream import action

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core import constants as core_constants

from ..models import MarketSubscription


@receiver(post_save, sender=MarketSubscription)
def handle_market_subscription(sender, instance, created, **kwargs):
    if not created:
        return

    kwargs = {
        'verb': core_constants.CUSTOMER_SUBSCRIBED,
        'target': instance.market,
    }

    if instance.creator_id:
        kwargs['agent_id'] = instance.creator_id

    action.send(instance.customer, **kwargs)


@receiver(post_delete, sender=MarketSubscription)
def handle_market_unsubscription(sender, instance, **kwargs):

    kwargs = {
        'verb': core_constants.CUSTOMER_UNSUBSCRIBED,
        'target': instance.market
    }

    if instance.last_editor_id:
        kwargs['agent_id'] = instance.last_editor_id

    action.send(instance.customer, **kwargs)
