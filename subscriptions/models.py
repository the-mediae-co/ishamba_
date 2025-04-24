
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from core.models import TimestampedBase
from core.utils.datetime import _one_year_from_today, _get_current_date
from customers.models import Customer
from subscriptions.managers import SubscriptionManager


class SubscriptionType(TimestampedBase):
    name = models.CharField(max_length=255, db_index=True)
    markets_allowance = models.PositiveIntegerField(blank=True, default=0)
    agri_tips_allowance = models.PositiveIntegerField(blank=True, default=0)
    prices_allowance = models.PositiveIntegerField(blank=True, default=0)
    is_permanent = models.BooleanField(
        db_index=True,
        default=False,
        help_text=_("Should subscriptions of this type ever expire?"),
    )
    is_premium = models.BooleanField(
        db_index=True,
        default=False,
        help_text=_("Should customers pay for this subscription?"),
    )
    end_message = models.TextField(
        blank=True,
        default='',
        help_text=_("Message to send when subscription expires."),
    )

    # External subscription types, e.g digifarm
    external_reference: str = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name



class Subscription(TimestampedBase):
    """
    Records a customer's subscription to the premium iShamba service.
    """
    customer = models.ForeignKey(Customer, verbose_name=_('customer'),
                                 related_name='subscriptions', on_delete=models.CASCADE)
    start_date = models.DateField(db_index=True, default=_get_current_date)
    end_date = models.DateField(
        db_index=True,
        default=_one_year_from_today,
        help_text=_("Note that the subscription period is inclusive of the "
                    "end date"))
    ended = models.BooleanField(db_index=True, default=False)
    type = models.ForeignKey(SubscriptionType, null=True, blank=True,
                             related_name='subscriptions', on_delete=models.CASCADE)
    extra = models.JSONField(blank=True, null=True)

    # External subscription, e.g digifarm
    external_reference: str = models.CharField(max_length=100, null=True, blank=True)

    objects = SubscriptionManager()

    @property
    def is_premium(self):
        """
        This deserves a more robust implementation
        """
        return self.type.is_premium

    def get_current_subscription_for_customer(customer):
        """
        Retrieves the current active subscription for the customer.
        """
        today = timezone.now().date()
        return Subscription.objects.filter(
            customer=customer,
            start_date__lte=today,
            end_date__gte=today,
            type__is_permanent=False
        ).first()

    @staticmethod
    def is_premium_customer(customer):
        """
        Checks if the customer has a current premium subscription.
        """
        subscription = Subscription.get_current_subscription_for_customer(customer)
        return subscription and subscription.type.is_premium


    class Meta:
        ordering = ('-end_date',)

    def __str__(self):
        return "{} subscription {} to {}".format(
            self.customer,
            self.start_date,
            self.end_date
        )


class SubscriptionAllowance(TimestampedBase):
    code = models.CharField(max_length=100, db_index=True)
    allowance = models.PositiveSmallIntegerField(default=0)
    type = models.ForeignKey(SubscriptionType,
                             on_delete=models.CASCADE,
                             related_name='allowances')

    def __str__(self):
        return self.code
