from typing import Tuple

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import Case, When, IntegerField, Value
from django.db.models.query import QuerySet
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from model_utils import Choices, FieldTracker
from sms.constants import OUTGOING_SMS_TYPE
from taggit.managers import TaggableManager

from core.models import TimestampedBase
from sms.tasks import send_message
from sms.utils import get_populated_sms_templates_text
from customers.models import CustomerCategory

import sentry_sdk


class Task(TimestampedBase):
    """
    Main model with which CCOs interact when processing incoming messages from
    Customers.
    """

    # field tracker used to track model changes
    tracker = FieldTracker()

    STATUS = Choices(
        ('new', _("New")),
        ('progressing', _("Progressing")),
        ('closed_resolved', _("Closed:Resolved")),
        ('closed_unresolved', _("Closed:Unresolved"))
    )

    PRIORITY = Choices(
        ('low', _("Low")),
        ('medium', _("Medium")),
        ('high', _("High")),
        ('critical', _("Critical")),
    )

    customer = models.ForeignKey('customers.Customer', verbose_name=_('customer'), related_name="tasks",
                                 on_delete=models.CASCADE)
    description = models.TextField(_('description'))

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    source = GenericForeignKey('content_type', 'object_id')

    outgoing_messages = models.ManyToManyField('sms.OutgoingSMS', blank=True)
    incoming_messages = models.ManyToManyField('sms.IncomingSMS')

    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                       verbose_name=_("Assignees"),
                                       blank=True)

    status = models.CharField(_('status'),
                              max_length=100,
                              choices=STATUS,
                              default=STATUS.new)
    priority = models.CharField(_("Priority"),
                                max_length=16,
                                choices=PRIORITY,
                                default='medium')

    contact_attempts = models.PositiveIntegerField(default=0, null=True)

    tags = TaggableManager(_("Tags"), blank=True)

    class Meta:
        permissions = [
            ("export", "Can export tasks"),
        ]

    def __str__(self):
        if self.pk:
            return "#{} {}".format(self.pk, self.description)
        else:
            return "New"

    def add_cannot_contact_customer_update(self, user):
        """
        Record that a CCO cannot contact the `Customer` and if a threshold
        is reached messages the `Customer` to notify them that we are
        attempting to contact them.
        """
        self.contact_attempts += 1

        if self.contact_attempts == settings.TASKS_CONTACT_FAILURES_BEFORE_SMS:
            # Avoiding circular import
            from sms.models import OutgoingSMS

            extra = {
                'task_id': self.id
            }
            # Let the customer know we're giving up
            text, sender = get_populated_sms_templates_text(settings.SMS_CANNOT_CONTACT_CUSTOMER, self.customer)
            msg = OutgoingSMS.objects.create(
                text=text,
                time_sent=timezone.now(),
                sent_by=user,
                extra=extra,
                message_type=OUTGOING_SMS_TYPE.TASK_RESPONSE,
            )
            send_message.delay(msg.id, [self.customer.id], sender=sender)
            self.outgoing_messages.add(msg)

    @property
    def is_closed(self):
        return self.status in (Task.STATUS.closed_resolved, Task.STATUS.closed_unresolved)

    @property
    def formatted_phone(self):
        return self.customer.formatted_phone

    @staticmethod
    def order_by_priority(queryset: QuerySet, is_descending: bool):
        """ Sorts the given queryset via priority """
        queryset = queryset.annotate(
            priority_int=Case(
                When(priority="low", then=0),
                When(priority="medium", then=1),
                When(priority="high", then=2),
                When(priority="critical", then=3),
                output_field=IntegerField(),
                default=Value(1)  # unspecified Tasks default to medium priority
            )).order_by(("-" if is_descending else "") + 'priority_int')
        return queryset, True


class TaskUpdate(TimestampedBase):
    """
    TaskUpdates record changes to Tasks including:
    - "Response updates": Where a CCO replies to the Customer.
    - "Status change updates": Where the CCO changes the status of a Task.
    - "Cannot contact customer updates": Where a CCO presses the "Cannot
      contact customer" button.
    - The user who made the corresponding change
    - The datetime of the change
    """
    UPDATE_TYPE_CHOICES = [
        ('cannot-contact', 'Cannot contact customer'),
    ]

    task = models.ForeignKey('Task', verbose_name=_('task'), on_delete=models.CASCADE)
    message = models.TextField(_('message'),
                               blank=True,
                               help_text=_("Markdown formatting is supported."))

    update_type = models.CharField(max_length=50,
                                   choices=UPDATE_TYPE_CHOICES,
                                   blank=True,
                                   null=True)

    status = models.CharField(_('status'),
                              max_length=100,
                              choices=Task.STATUS)

    def __str__(self):
        return "{}".format(self.created)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.status:
            self.status = self.previous_status

    @property
    def previous_status(self) -> Tuple:
        """
        Returns:
            The status of the previous TaskUpdate defaulting to Task.STATUS.new
            if no previous updates exist.
        """
        reference_time = self.created or timezone.now()
        try:
            return (self.task.taskupdate_set.exclude(pk=self.pk)
                                            .filter(created__lte=reference_time)
                                            .latest('created').status)
        except TaskUpdate.DoesNotExist:
            return Task.STATUS.new

    @property
    def status_changed(self):
        """
        Returns:
            A dictionary with keys 'from' and 'to' representing the change in
            status if the status has changed. Otherwise False.
        """
        previous_status = self.previous_status
        current_status = self.status

        if previous_status == current_status:
            return False

        return {'from': previous_status, 'to': current_status}

    # def save(self, *args, **kwargs):
    #     # Ensure at least the status is changed or a message is entered.
    #     # Otherwise raise a ValidationError.
    #     if not any((self.message, self.status_changed)):
    #         raise ValidationError(
    #             "Either enter a message, or change the status, otherwise this "
    #             "update is doing nothing.")
    #     return super().save(*args, **kwargs)


# Connect TaskUpdate object saves to actionstream changes
# def _task_update_changed_callback(sender, instance, **kwargs):
    # task = instance.task
    # task.status = task.taskupdate_set.latest('created').status
    # task.last_editor_id = instance.creator_id  # Ensure the last_editor_id of the task is recorded
    # task.save(update_fields=['status', 'last_editor_id'])


# post_save.connect(_task_update_changed_callback, sender=TaskUpdate)
