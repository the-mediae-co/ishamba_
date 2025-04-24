from typing import Optional
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django_tenants.models import TenantMixin, DomainMixin


class TimestampedBase(models.Model):
    """
    Timestamping features in an abstract class, for inheritance
    ALSO: we want to track the creating and last editing User, but because
    this is an abstract class, the FK relation won't work. Instead, we're
    denorming the relevant user ID and providing a convenient accessor
    which should work across all subclassing models.
    So, whenever saving a TimestampBased model, pass in the active user
    object as a kwarg to save(), eg:
    foo.save(user=request.user)
    """

    created = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    creator_id = models.IntegerField(blank=True, null=True)

    last_updated = models.DateTimeField(blank=True, null=True, auto_now=True)
    last_editor_id = models.IntegerField(blank=True, null=True)

    class Meta:
        abstract = True

    @property
    def creator(self):
        return _get_creator_or_editor(self.creator_id)

    @property
    def last_editor(self):
        return _get_creator_or_editor(self.last_editor_id)

    def save(self, *args, **kwargs):
        """
        Captures the acting user, via 'user' keyword argument
        """
        user = kwargs.pop('user', None)
        if user:
            self.last_editor_id = user.id
        if user and not self.creator_id:
            self.creator_id = user.id

        return super().save(*args, **kwargs)


# generic function, not an object method
def _get_creator_or_editor(_id):
    User = get_user_model()
    try:
        return User.objects.get(id=_id)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        return None


# https://django-tenants.readthedocs.io/en/latest/install.html#the-tenant-domain-model
class Client(TenantMixin, TimestampedBase):
    name = models.CharField(max_length=100)
    at_api_key = models.CharField(max_length=100)
    at_username = models.CharField(max_length=100)
    at_sender = models.CharField(max_length=100)
    pusher_app_id = models.CharField(max_length=100)
    pusher_key = models.CharField(max_length=100)
    pusher_secret = models.CharField(max_length=100)
    accept_only_registered_calls = models.BooleanField(default=True)
    voice_queue_number = models.CharField(max_length=100)
    voice_dequeue_number = models.CharField(max_length=100)
    sms_shortcode = models.PositiveIntegerField()
    mpesa_till_number = models.CharField(max_length=100, null=True, blank=True)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2)
    yearly_price = models.DecimalField( max_digits=12, decimal_places=2)
    send_weather = models.BooleanField(default=False)
    tip_reports_to = models.TextField()
    tips_enabled = models.BooleanField(default=True)

    @property
    def domain(self) -> Optional[str]:
        primary_domain = self.get_primary_domain()
        return f"https://{primary_domain.domain}" if primary_domain else None

    @property
    def hold_recording(self) -> str:
        return f"calls/audio/{self.name}/hold.mp3"

    @property
    def inactive_recording(self) -> str:
        return f"calls/audio/{self.name}/inactive.mp3"

    @property
    def closed_recording(self) -> str:
        return f"calls/audio/{self.name}/closed.mp3"

    @property
    def premium_only_recording(self) -> str:
        return f"calls/audio/{self.name}/premium_only.mp3"

    @property
    def logo(self) -> str:
        return f"images/{self.name}/logo.png"


# https://django-tenants.readthedocs.io/en/latest/install.html#the-tenant-domain-model
class Domain(DomainMixin):
    pass
