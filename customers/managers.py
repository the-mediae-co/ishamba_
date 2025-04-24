from django.contrib.gis.db import models
from django.db.models import Case, Q, Sum, When, QuerySet
from django.utils import timezone

from core.utils.clients import client_setting

from agri.models.base import Commodity


def count_if(*args, **kwargs):
    """
    Conditional count.
    """
    kwargs['then'] = 1

    return Sum(
        Case(
            When(*args, **kwargs),
            default=0,
            output_field=models.IntegerField()
        )
    )


# NOTE: Though this module is called managers we subclass QuerySet (or
# it's subclasses) and use .as_manager() for convenience.


class CustomerQuerySet(QuerySet):
    """
    Adds .should_receive_messages() and .can_access_call_centre() QuerySets
    which should be used in preference to more granular checking elsewhere.

    Note: since Customer has geo fields we subclass GeoQuerySet to preserve the
    appropriate inheritance.
    """
    def premium(self, date=None):
        """ QuerySet of Customers with active premium subscriptions.  """

        date = date or timezone.now().date()
        return (self.filter(Q(subscriptions__start_date__lte=date)
                            & Q(subscriptions__end_date__gte=date)
                            & Q(subscriptions__type__is_premium=True)).distinct())

    def non_premium(self, date=None):
        """ QuerySet of Customers without active premium subscriptions.  """
        date = date or timezone.now().date()
        return (self.exclude(Q(subscriptions__start_date__lte=date)
                             & Q(subscriptions__end_date__gte=date)
                             & Q(subscriptions__type__is_premium=True)).distinct())

    def freemium(self):
        """ QuerySet of Customer's who are not subscribed """
        today = timezone.now().date()
        return self.filter(subscriptions__type__is_premium=False, subscriptions__end_date__gte=today).distinct()

    def should_receive_messages(self):
        return self.filter(
            has_requested_stop=False,
            digifarm_farmer_id__isnull=True,
            phones__isnull=False
        )

    def can_access_call_centre(self):
        qs = self.filter(has_requested_stop=False)
        if client_setting('accept_only_registered_calls'):
            qs = qs.filter(is_registered=True)
        return qs

    def should_receive_tips(self):
        return (self.should_receive_messages()
                    .filter(tip_subscriptions__isnull=False)
                    .distinct())

    def cannot_receive_market_prices(self):
        """
        Note, this does not test whether the customers are active, stopped, or
        otherwise, so in practice use this QuerySet only in combination with
        others such as should_receive_messages etc.

        Returns:
            Customers who either have no commodity subscriptions, or no market
            subscriptions, or whose every commodity subscription is set not to
            send prices.
        """
        return self.filter(Q(market_subscriptions=None) | Q(commodities=None))

    def can_receive_market_prices(self):
        """
        Note, this does not test whether the customers are active, stopped, or
        otherwise, so in practice use this queryset only in combination with
        others such as should_receive_messages etc.

        Returns customers who have commodity subscriptions, where at least one
        of their commodity subscirptions is set to send prices, and who have at
        least one market subscription.
        """
        return (
            self.exclude(market_subscriptions=None).exclude(commodities=None)
        )

    def digifarm_only(self):
        """ QuerySet of digifarm farmers """
        return self.filter(
            digifarm_farmer_id__isnull=False,
            phones__isnull=True,
            phone_number_hash__isnull=False
        ).distinct()

    def africas_talking_only(self):
        """
        Returns customers who have not been moved to digifarm
        """
        return self.filter(digifarm_farmer_id=None)

    def filter_by_phones(self, phones):
        """
        Returns customers with a matching phone number
        """
        return self.filter(phones__number__in=phones).values('customers')

    def phones_list(self):
        return self.values_list('phones__number')


class CommoditySubscriptionQuerySet(models.QuerySet):
    """
    Adds:
        - the `.calendar_based()` queryset which returns either subscriptions
          to seasonal commodities or ended date-based ones
        - the `.event_based()` queryset which returns all non-ended event-based
          subscriptions
    """
    def calendar_based(self):
        return self.filter(Q(epoch_date=None) | Q(ended=True))

    def event_based(self):
        return self.exclude(epoch_date=None).filter(ended=False)

    def crop_subscriptions(self):
        return self.filter(commodity__commodity_type=Commodity.CROP)

    def livestock_subscriptions(self):
        return self.filter(commodity__commodity_type=Commodity.LIVESTOCK)

    def count_subscription_uses(self):
        counts = self.aggregate(
            prices=count_if(
                send_market_prices=True
            ),
            tips=count_if(
                send_agri_tips=True
            )
        )
        # Zero occurences will be returned as None, so default to 0
        return {k: v or 0 for k, v in counts.items()}


class CommoditySubscriptionManager(models.Manager.from_queryset(CommoditySubscriptionQuerySet)):
    use_for_related_fields = True
