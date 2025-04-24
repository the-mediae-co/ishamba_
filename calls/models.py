from typing import Optional
from django.conf import settings
from django.db import models
from django.utils import timezone

import phonenumbers
from phonenumber_field.modelfields import PhoneNumberField

from callcenters.models import CallCenter, CallCenterOperator


class CallQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def queued(self):
        return self.filter(is_active=True, connected=False)

    def connected(self):
        return self.filter(is_active=True, connected=True)

    def finished(self):
        return (self.filter(is_active=False, connected=False)
                    .exclude(duration=0))

    def dropped(self):
        return self.filter(is_active=False, connected=False, duration=0)


class Call(models.Model):
    """
    Call states
     - New call: is_active = True, connected = False, duration = None
     - Currently talking call: is_active = True, connected = True,
       duration = None
     - Successfully Finished call: is_active = False, connected = False,
       duration = real duration
     - Call dropped before talking: is_active = False, connected = False,
       duration = 0
    """

    created_on = models.DateTimeField(auto_now_add=True)
    connected_on = models.DateTimeField(blank=True, null=True)
    hanged_on = models.DateTimeField(blank=True, null=True)
    provided_id = models.CharField(max_length=100)
    caller_number = models.CharField(max_length=100)
    destination_number = models.CharField(max_length=100)
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE)
    direction = models.CharField(max_length=100)
    duration = models.PositiveSmallIntegerField(blank=True, null=True)
    duration_in_queue = models.PositiveSmallIntegerField(blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=5,
                               blank=True, null=True)
    cco = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True,
                            verbose_name='CCO', on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=False)
    connected = models.BooleanField(default=False)
    issue_resolved = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    # Sort of a cache for self.customer.call_center
    # Avoids expensive joins when querying calls for a call center
    call_center = models.ForeignKey(
        CallCenter,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='calls'
    )

    objects = CallQuerySet.as_manager()

    @property
    def previous_calls_number(self):
        return (Call.objects.filter(caller_number=self.caller_number,
                                    created_on__lt=self.created_on).count())

    def connect(self, cco, commit=True):
        """ Sets a call to 'currently talking'. """
        self.is_active = True
        self.connected = True
        self.cco = cco
        self.connected_on = timezone.now()
        if commit:
            self.save(update_fields=['is_active', 'connected', 'cco',
                                     'connected_on'])

    def hangup(self, commit=True):
        """ Sets call to 'hung up' but *does not* update call statistics. """
        self.is_active = False
        self.connected = False
        self.hanged_on = self.hanged_on or timezone.now()

        if commit:
            self.save(update_fields=['is_active', 'connected', 'hanged_on'])


class CallCenterPhoneQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def is_active_phone(self, phone):
        return self.active().filter(phone_number=phone).exists()


class CallCenterPhone(models.Model):
    is_active = models.BooleanField(default=True)
    phone_number = PhoneNumberField(unique=True)
    operators = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                       through='PusherSession', blank=True)

    objects = CallCenterPhoneQuerySet.as_manager()

    def __str__(self):
        return self.format_phone_number()

    def format_phone_number(self, number_format='INTERNATIONAL'):
        phone_number_format = getattr(phonenumbers.PhoneNumberFormat,
                                      number_format)
        return phonenumbers.format_number(self.phone_number,
                                          phone_number_format)

    @property
    def current_operator(self):
        try:
            return PusherSession.objects.connected().get(call_center_phone=self).operator
        except PusherSession.DoesNotExist:
            return None


class PusherSessionManager(models.Manager):
    def connected(self):
        return (self.get_queryset().exclude(pusher_session_key__isnull=True)
                                   .exclude(pusher_session_key__exact='')
                                   .filter(finished_on__isnull=True))

    def finished(self):
        return self.get_queryset().exclude(finished_on__isnull=True)

    def empty_call_center(self):
        return not self.connected().exists()


class PusherSession(models.Model):
    """
    An active PusherSession represents the state of a CCO (user) being
    currently logged in to the call centre, and able to make calls using a
    number represented by a CallCenterPhone object.
    """
    call_center_phone = models.ForeignKey('CallCenterPhone', on_delete=models.CASCADE)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provided_call_id = models.CharField(max_length=100, null=True)

    pusher_session_key = models.CharField(max_length=50)
    created_on = models.DateTimeField(auto_now_add=True)
    finished_on = models.DateTimeField(blank=True, null=True)

    objects = PusherSessionManager()

    def get_priority_call_center(self) -> Optional[CallCenter]:
        current_call_center = CallCenterOperator.objects.filter(
            operator=self.operator, active=True
        ).order_by('-current', '-id').first()
        if current_call_center:
            return current_call_center.call_center
        return None
