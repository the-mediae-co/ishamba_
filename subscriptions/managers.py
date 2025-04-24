import datetime
from collections import defaultdict
from itertools import groupby

from django.db import models
from django.utils import timezone

class SubscriptionQuerySet(models.QuerySet):

    def permanent(self):
        return self.filter(type__is_permanent=True)

    def not_permanent(self):
        return self.exclude(type__is_permanent=True)

    def has_end_message(self):
        return self.exclude(type__end_message='')

    def active(self, date: datetime.date = None):
        date = date or timezone.now().date()
        active = self.filter(start_date__lte=date, end_date__gte=date)
        return self.permanent() | active

    def not_ended(self):
        return self.exclude(ended=True)

    def expired(self, date: datetime.date = None):
        date = date or timezone.now().date()
        return self.filter(end_date__lt=date)

    def current_by_date(self, date: datetime.date = None):
        date = date or timezone.now().date()
        active = self.filter(start_date__lte=date, end_date__gte=date)
        return active

    def potent(self, date: datetime.date = None):
        """
        Returns all subscriptions either active or not-yet-started on a
        given date.
        """
        date = date or timezone.now().date()
        return self.permanent() | self.filter(end_date__gte=date)

    def first_by_customer(self):
        return self.order_by('customer', 'start_date').distinct('customer')

    def latest_by_customer(self):
        return self.order_by('customer', '-end_date').distinct('customer')

    def get_usage_allowance(self, allowance):
        """
        Retrieves the allowance for the given allowance code.

        Args:
            allowance: Allowance code to lookup

        Returns:
            int representing the allowance
        TODO: The summing and query should be done in db to avoid the imports
        reverse query with self.model should be workable
        """
        from subscriptions.models import SubscriptionAllowance
        type_pks = self.values_list('type', flat=True)
        allowances = SubscriptionAllowance.objects.filter(type__in=type_pks, code=allowance)
        return self.sum_allowances(allowances, type_pks).get(allowance, 0)

    @staticmethod
    def sum_allowances(allowances, type_pks):
        """
        Excepts a SubscriptionAllowance queryset
        """
        tuples = allowances.order_by('type').values_list('type', 'code', 'allowance')
        types = {key: list(group) for key, group in groupby(tuples, key=lambda x: x[0])}
        totals = defaultdict(int)
        for type_pk in type_pks:
            for _, code, value in types.get(type_pk, []):
                totals[code] += value
        return totals

    def count_usage_allowances(self):
        """
        Counts all the allowances for the subscriptions. If none of the
        available subscriptions has one of the allowances it is defaulted
        to 0.

        Returns:
            dict mapping the allowance codes to their counts.
        """
        from subscriptions.models import SubscriptionAllowance
        type_pks = self.values_list('type', flat=True)
        allowances = SubscriptionAllowance.objects.filter(type__in=type_pks)
        return self.sum_allowances(allowances, type_pks)


class SubscriptionManager(models.Manager.from_queryset(SubscriptionQuerySet)):
    use_for_related_fields = True
