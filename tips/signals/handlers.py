from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from actstream import action

from core import constants as core_constants
from .. import models


@receiver(post_save, sender=models.TipSent)
def handle_tip_sent(sender, instance, created, **kwargs):
    if not created:
        return

    kwargs = {
        'sender': instance.subscription.customer,
        'verb': core_constants.ACTIVITY_TIP_SENT,
        'action_object': instance,
    }

    action.send(**kwargs)


@receiver(post_save, sender=models.TipSeriesSubscription)
def handle_tipseries_subscription(sender, instance, created, **kwargs):
    # First, make sure the commodity for this subscription is added to the
    # customer's commodities set (whether this is a new or modified subscription)
    customer = instance.customer
    commodity = instance.series.commodity
    if customer is not None and commodity is not None:
        customer.commodities.add(commodity)

    # Then, if a new subscription was added, add an actstream action
    if not created:
        return

    kwargs = {
        'verb': core_constants.CUSTOMER_SUBSCRIBED,
        'target': instance.series,
    }

    if instance.creator_id:
        kwargs['agent_id'] = instance.creator_id

    action.send(instance.customer, **kwargs)


@receiver(post_delete, sender=models.TipSeriesSubscription)
def handle_tipseries_unsubscription(sender, instance, **kwargs):

    kwargs = {
        'verb': core_constants.CUSTOMER_UNSUBSCRIBED,
        'target': instance.series
    }

    if instance.last_editor_id:
        kwargs['agent_id'] = instance.last_editor_id

    action.send(instance.customer, **kwargs)
