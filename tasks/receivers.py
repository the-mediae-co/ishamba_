from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from actstream import action

from .models import Task
from .tags import collapse_tags


@receiver(post_save, sender=Task)
def store_activity(sender, instance, created, **kwargs):
    """ Generates actions based on the modifications made to the model.
    """
    # by definition there has been no modification if the instance was newly
    # created and actions are preformed by an actor so make sure we have one
    if created or not instance.last_editor:
        return

    # Report changes in the following fields
    for field in ('status', 'priority'):
        if instance.tracker.has_changed(field):
            action.send(instance.last_editor,
                        verb='changed',
                        target=instance,
                        field=field,
                        initial=instance.tracker.previous(field),
                        final=getattr(instance, field, None))

    # Report contact attempt count
    if instance.tracker.has_changed('contact_attempts'):
        action.send(instance.last_editor,
                    verb='contact_failed',
                    target=instance,
                    field='contact_attempts',
                    attempt=getattr(instance, 'contact_attempts', None))


@receiver(m2m_changed, sender=Task.tags.through)
def store_tags_activity(sender, instance, model, pk_set, **kwargs):
    """ Generates actions when the m2m relation `Task.tags` is modified.
    """
    # the through model is generic so this handler will be called no matter
    # what object is being tagged. We only want to register activity when a
    # `Task` is being tagged.
    if type(instance) is not Task:
        return

    # actions are preformed by an actor so make sure we have one
    if not instance.last_editor:
        return

    # check we actually got some tags here
    if not pk_set:
        return

    m2m_action = kwargs.get('action')
    if m2m_action in ('pre_add', 'pre_remove'):
        verb = 'tagged' if m2m_action == 'pre_add' else 'untagged'

        tag_names = [t.name for t in
                     collapse_tags(model.objects.filter(pk__in=list(pk_set)))]

        action.send(instance.last_editor,
                    verb=verb,
                    target=instance,
                    tags=list(tag_names))


@receiver(m2m_changed, sender=Task.assignees.through)
def store_assignees_activity(sender, instance, model, pk_set, **kwargs):
    """ Generates actions when the m2m relation `Task.assignees` is modified.
    """
    # actions are preformed by an actor so make sure we have one
    if not instance.last_editor:
        return

    m2m_action = kwargs.get('action')

    if m2m_action in ('pre_add', 'pre_remove'):
        verb = 'assigned' if m2m_action == 'pre_add' else 'unassigned'
        for pk in pk_set:
            action.send(instance.last_editor,
                        verb=verb,
                        target=instance,
                        action_object=model.objects.get(pk=pk))


@receiver(m2m_changed, sender=Task.incoming_messages.through)
def store_incoming_message_activity(sender, instance, model, pk_set, **kwargs):
    """ Generates actions when the m2m relation `Task.incoming_messages` is
    modified.
    """
    # actions are preformed by an actor so make sure we have one
    m2m_action = kwargs.get('action')

    if m2m_action == 'post_add':
        for pk in pk_set:
            obj = model.objects.get(pk=pk)
            action.send(obj.customer,
                        verb='sent',
                        target=instance,
                        action_object=obj,
                        timestamp=obj.at)


@receiver(m2m_changed, sender=Task.outgoing_messages.through)
def store_outgoing_message_activity(sender, instance, model, pk_set, **kwargs):
    """ Generates actions when the m2m relation `Task.outgoing_messages` is
    modified.
    """
    # actions are preformed by an actor so make sure we have one
    m2m_action = kwargs.get('action')

    if m2m_action == 'post_add':
        for pk in pk_set:
            obj = model.objects.get(pk=pk)
            action.send(obj.sent_by,
                        verb='sent',
                        target=instance,
                        action_object=obj,
                        timestamp=obj.time_sent)
