
from django.db import models



class CallCenterQuerySet(models.QuerySet):

    def for_operator(self, operator):
        """
        Returns the currently active CallCenter for the given User
        """
        from callcenters.models import CallCenterOperator

        operator = CallCenterOperator.objects.filter(operator=operator, active=True).order_by('-current', '-id').first()

        if not operator:
            return None

        return operator.call_center
