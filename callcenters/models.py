from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify

from callcenters.managers import CallCenterQuerySet
from world.models import Border, BorderLevelName


User = get_user_model()


class CallCenterSender(models.Model):
    sender_id = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.sender_id


class CallCenter(models.Model):
    name: str = models.CharField(max_length=50, unique=True)
    description: str = models.TextField(blank=True, null=True)
    border: Border = models.OneToOneField(
        Border,
        related_name='call_center',
        on_delete=models.RESTRICT,
        limit_choices_to={'level__in': [0,1]}
    )
    senders = models.ManyToManyField(CallCenterSender, related_name='call_centers')

    objects = CallCenterQuerySet.as_manager()

    @property
    def queue_name(self):
        return slugify(self.name)

    @property
    def country(self):
        if self.border.level == 0:
            return self.border
        return self.border.parent

    @property
    def country_name(self):
        return self.border.country

    @property
    def phone_number_prefix(self) -> str:
        return self.border.phone_number_prefix

    def __str__(self) -> str:
        return f"{self.name}: {self.border}"


class CallCenterOperator(models.Model):
    operator: User = models.ForeignKey(
        User, related_name='call_center_operators',
        on_delete=models.CASCADE
    )
    call_center: CallCenter = models.ForeignKey(
        CallCenter, related_name='call_center_operators',
        on_delete=models.CASCADE
    )
    current: bool = models.BooleanField(default=False)
    active: bool = models.BooleanField(default=True)

    class Meta:
        unique_together = (('call_center', 'operator'))

    def __str__(self) -> str:
        return f"{self.operator}: {self.call_center}"

    @property
    def name(self) -> str:
        return self.call_center.name

    @property
    def border_id(self) -> str:
        return self.call_center.border_id

    @property
    def border_level(self) -> str:
        return self.call_center.border.level

    def to_dict(self) -> dict:
        return {
            'call_center_id': self.call_center_id,
            'name': self.name,
            'border_id': self.border_id,
            'border_level': self.border_level,
            'country': self.call_center.country_name,
            'border_level_name': list(
                BorderLevelName.objects.filter(
                    country=self.call_center.country_name
                ).values_list('name', flat=True)
            )
        }
