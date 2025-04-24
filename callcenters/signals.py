from typing import Any, Type

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.http import HttpRequest

from callcenters.models import CallCenterOperator


@receiver(user_logged_in)
def set_current_call_center(sender: Type[User], user: User, request: HttpRequest, **kwargs: Any):
    user_call_centers = CallCenterOperator.objects.filter(operator=user)
    if not user_call_centers.exists():
        return

    if user_call_centers.filter(operator=user, current=True).exists():
        return

    # The last call center the user was added to is marked as current
    last_call_center = user_call_centers.last()
    last_call_center.current = True
    last_call_center.save()
