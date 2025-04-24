import json
import sentry_sdk
from datetime import date
from typing import Iterable

from django.conf import settings
from django.utils.functional import cached_property
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _
from django.db import connection

from celery.utils.log import get_task_logger
from tenant_schemas_celery.task import TenantTask

from ishamba.celery import app
from core.utils.datetime import first_day_of_iso_week_date_year, midnight
from customers.models import CommoditySubscription, Customer
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS
from sms.tasks import send_message

from . import constants
from .models import Commodity, Region
from .models.messaging import AgriTipSMS

logger = get_task_logger(__name__)


class SendTipsBase(TenantTask):
    """ Base Task for agri-tip sending. """
    ignore_results = True

    def __init__(self, *args, **kwarg):
        super().__init__(*args, **kwarg)
        sentry_sdk.capture_message(f"SendTipsBase being instantiated.")
        raise DeprecationWarning(f"SendTipsBase is deprecated. Use tips/TipSeries as a replacement.")

    def setup(self, *args, **kwargs):
        customer_pks = kwargs.get('customers')
        if customer_pks:
            self.customers = self.load_customers(customer_pks)
        else:
            self.customers = Customer.objects.should_receive_agri_tips()

        self.today = midnight(localtime(now()))
        # calculate the tip number of the tips to be sent
        __, weeknumber, __ = self.today.isocalendar()
        self.tipnumber = weeknumber // settings.AGRI_TIPS_SENDING_PERIOD

        # fetch all subscriptions
        self.all_subscriptions = CommoditySubscription.objects.filter(
            send_agri_tips=True, subscriber__in=self.customers)

    @staticmethod
    def generate_commodity_variant_map():
        commodities = Commodity.objects.values_list('pk', 'variant_of_id')
        return {pk: variant for pk, variant in commodities}

    @staticmethod
    def load_customers(customer_pks):
        return Customer.objects.filter(pk__in=customer_pks)


class SendCropTipsBase(SendTipsBase):
    def __init__(self, *args, **kwarg):
        super().__init__(*args, **kwarg)
        sentry_sdk.capture_message(f"SendCropTipsBase being instantiated.")
        raise DeprecationWarning(f"SendCropTipsBase is deprecated. Use tips/TipSeries as a replacement.")

    @cached_property
    def customer_regions(self):
        """ Returns the Agricultural Regions associated with self.customers. """
        regions = (self.customers.exclude(agricultural_region=None)
                                 .values_list('agricultural_region', flat=True)
                                 .distinct())

        return Region.objects.filter(pk__in=regions)


# @app.task(base=SendCropTipsBase, bind=True, ignore_result=True)
def send_crop_tips(self, *args, **kwargs):
    """ Sends crop tips. """
    self.setup(*args, **kwargs)

    subscription_pks = (self.all_subscriptions
                            .crop_subscriptions()
                            .values_list('pk', flat=True))

    # get the crop commodities for which to send out tips
    commodities = Commodity.objects.filter(
        commoditysubscription__in=subscription_pks
    ).distinct().values_list('pk', 'variant_of__pk')

    logger.info('Sending crop tips for %d commodities', len(commodities))
    for commodity_pk, variant_of__pk in commodities:
        # get only those agricultural_regions containing customers in the customers
        # queryset subscribed to this commodity
        region_pks = self.customer_regions.filter(
            customer__commodity_subscriptions=commodity_pk
        ).values_list('pk', flat=True).distinct()

        for region_pk in region_pks:
            # Get the recipients for the commodity and region
            recipients = self.customers.filter(
                commodity_subscriptions=commodity_pk,
                region_id=region_pk
            )

            if recipients:
                # Use variant for the tips if set
                commodity_pk = variant_of__pk or commodity_pk
                send_agri_tip_sms.delay(commodity_pk, self.tipnumber,
                                        recipients, region_pk=region_pk)
    logger.debug('Finished sending crop tips')


# @app.task(base=SendTipsBase, bind=True, ignore_result=True)
def send_event_based_livestock_tips(self, *args, **kwargs):
    """ Sends event based livestock tips. """
    self.setup(*args, **kwargs)

    subscriptions = (
        self.all_subscriptions
        .livestock_subscriptions()
        .event_based()
        .values_list('epoch_date', 'subscriber__pk', 'commodity_id')
    )

    today = self.today.date()
    commodities = self.generate_commodity_variant_map()

    logger.info('Sending event based livestock tips for %d subscriptions',
                 len(subscriptions))
    for subscription in subscriptions:
        epoch_date, subscriber_pk, commodity_pk = subscription

        tipnumber = CommoditySubscription.get_relative_tip_number(
            epoch_date, date=today)

        earliest_date = AgriTipSMS.earliest_date_for_relative_tip(
            epoch_date, tipnumber)

        subscriber = Customer.objects.filter(pk=subscriber_pk)  # Using filter() instead of get() to keep it a QuerySet

        send_agri_tip_sms.delay(
            commodities[commodity_pk] or commodity_pk,
            tipnumber,
            subscriber,
            earliest_date=earliest_date)
    logger.debug('Finished sending event based livestock tips')


# @app.task(base=SendTipsBase, bind=True, ignore_result=True)
def graduate_event_based_subscriptions(self, *args, **kwargs):
    """ Graduates event based subscriptions that we have no tips for. """
    self.setup(*args, **kwargs)

    logger.debug("Starting subscription graduation")
    subscriptions = (self.all_subscriptions
                         .livestock_subscriptions()
                         .event_based()
                         .values_list('pk', 'epoch_date', 'commodity_id',
                                      'subscriber__pk'))

    ended_pks = []
    today = self.today.date()
    commodities = self.generate_commodity_variant_map()

    # Find subscriptions that have expired
    for subscription in subscriptions:
        pk, epoch_date, commodity_pk, subscriber_pk = subscription

        # Find the relative tip number
        tipnumber = (CommoditySubscription.get_relative_tip_number(
            epoch_date, date=today))

        # Find the tip source pk
        commodity_pk = commodities[commodity_pk] or commodity_pk

        # Are there tips left for this subscription?
        requires_graduation = not AgriTipSMS.objects.filter(
            commodity_id=commodity_pk,
            number__gte=tipnumber
        ).exists()
        if requires_graduation:
            commodity = Commodity.objects.get(pk=commodity_pk)
            ended_pks.append(pk)
            subscriber = Customer.objects.filter(pk=subscriber_pk)
            send_subscription_expired.delay(subscriber,
                                            commodity.name,
                                            commodity.fallback_commodity.name,
                                            epoch_date)

    # Update all the ended subscriptions we have found
    logger.info(_("Graduating {} subscriptions".format(len(ended_pks))))
    (CommoditySubscription.objects.filter(pk__in=ended_pks)
                                  .update(ended=True))


# @app.task(base=SendTipsBase, bind=True, ignore_result=True)
def send_calendar_based_livestock_tips(self, *args, **kwargs):
    """
    Send calendar based livestock tips.

    IMPORTANT: This task should be run as a callback to
    `agri.tasks.graduate_expiring_subscriptions`
    """
    self.setup(*args, **kwargs)
    subscriptions = (self.all_subscriptions
                         .livestock_subscriptions()
                         .calendar_based())
    commodities = Commodity.objects.filter(
        commoditysubscription__in=subscriptions
    ).distinct().only('pk', 'epoch_description', 'fallback_commodity')

    # No need to get regions: livestock agri-tip streams are universal
    logger.debug('Sending calender based livestock tips for %d commodities',
                 commodities.count())
    for commodity in commodities:
        subscriber_ids = subscriptions.filter(commodity=commodity)\
            .values_list('subscriber__pk', flat=True)
        recipients = Customer.objects.filter(id__in=subscriber_ids)

        if recipients:
            # Check if this was previously an event-based subscription and
            # if so use the fallback (calendar-based) commodity instead.
            if commodity.is_event_based:
                commodity = commodity.fallback_commodity
            logger.debug('Sending commodity %(commodity_id)d tip '
                         '#%(tipnumber)d to %(num_recipients)d',
                         {'commodity_id': commodity.agri_tip_source.pk,
                          'tipnumber': self.tipnumber,
                          'num_recipients': len(recipients)})
            send_agri_tip_sms.delay(
                commodity.agri_tip_source.pk,
                self.tipnumber,
                recipients
            )
    logger.debug('Finished sending calender based livestock tips')


# @app.task(ignore_result=True)
def send_scheduled_tips():
    """
    The scheduled sending of agri-tips SMSs to all subscribed customers.

    This task should be called on any desired schedule. Built-in checks
    will prevent a tip from being sent more than once per year to any one user.
    """
    send_crop_tips.delay()
    graduate_event_based_subscriptions.apply_async(
        link=[send_calendar_based_livestock_tips.si(),
              send_event_based_livestock_tips.si()]
    )


# @app.task(ignore_result=True)
def send_agri_tip_sms(commodity_pk, tip_number: int, recipients: Iterable[Customer],
                      region_pk=None, earliest_date=None):
    """
    Send the tip for a given commodity, tip number and region (optional) to
    the given recipients.

    Retrieves a recent pre-existing OutgoingSMS with the correct
    properties (or create a new one). If a pre-existing OutgoingSMS is
    found then that will be used to stop customer receiving the same tip
    again.

    Args:
        commodity_pk: `Commodity` primary key to get `AgriTipSMS` by
        tip_number (int): Tip number to get `AgriTipSMS` by
        recipients (iterable): QuerySet or List of Customer objects
        region_pk: Optional `Region` primary key to get `AgriTipSMS` by
        earliest_date: Optional limit on when to check for previously sent tips,
            defaults to the earliest day in the current year.
    """
    try:
        tip = AgriTipSMS.objects.get(commodity_id=commodity_pk,
                                     number=tip_number,
                                     region_id=region_pk)
        tip_pk = tip.pk
        tip_text = tip.text
    except AgriTipSMS.DoesNotExist as e:
        logger.exception(e, extra={'commodity_pk': commodity_pk,
                                   'tip_number': tip_number,
                                   'region_pk': region_pk})
        return

    if earliest_date is None:
        # Get the relevant SMS object from this year to ensure
        # we're not getting a record from a previous year.
        today = midnight(localtime(now()))
        earliest_date = first_day_of_iso_week_date_year(today)

    # update earliest date to be a localised datetime
    earliest_date = midnight(localtime(now()).replace(
        day=earliest_date.day,
        month=earliest_date.month,
        year=earliest_date.year))

    extra = {
        'tip_id': tip_pk,
        'tip_number': tip_number,
        'tip_text': tip_text,
    }
    if commodity_pk and tip.commodity:
        extra.update({
            'commodity_id': commodity_pk,
            'commodity_name': tip.commodity.name,
        })
    if region_pk and tip.agricultural_region:
        extra.update({
            'region_id': region_pk,
            'region_name': tip.agricultural_region.name,
        })

    try:
        # retrieve or create an OutgoingSMS for the given tip
        outgoing_sms, __ = OutgoingSMS.objects.filter(
            created__gte=earliest_date,
            message_type=OUTGOING_SMS_TYPE.AGRI_TIP,
        ).get_or_create(tip_id=tip_pk, defaults={'text': tip_text, 'extra': extra})
    except OutgoingSMS.MultipleObjectsReturned:
        # Best explanation for this situation is two customers who have
        # the same event-based commodity subscription with similar
        # event dates. The earliest subscription's OutgoingSMS
        # object already exists, and may be within the search range.
        # We choose the earliest on the presumption that if any
        # OutgoingSMS for this tip has been sent recently then the
        # earliest is the only possible match. It's a bit risky, but
        # temporary, and it passes tests.
        outgoing_sms = OutgoingSMS.objects.filter(created__gte=earliest_date,
                                                  message_type=OUTGOING_SMS_TYPE.AGRI_TIP,
                                                  tip_id=tip_pk).earliest('created')

    # sent the `OutgoingSMS` to the given list of recipients
    send_message.delay(outgoing_sms.id, list(recipients.values_list('id', flat=True)), sender=settings.SMS_SENDER_AGRITIP)

    # set the time_sent if it hasn't been set already
    if not outgoing_sms.time_sent:
        outgoing_sms.time_sent = localtime(now())
        outgoing_sms.save(update_fields=['time_sent'])


# @app.task(ignore_result=True)
def send_subscription_expired(customers: Iterable[Customer],
                              commodity_name, new_commodity_name,
                              epoch_date: date):
    """
    Sends a subscription expired message for a customer whose event based
    subscription has expired.
    """
    # construct msg
    msg = constants.GRADUATION_MSG.format(old=commodity_name,
                                          new=new_commodity_name)
    extra = {
        'commodity_name': commodity_name,
        'new_commodity_name': new_commodity_name,
    }
    if epoch_date:
        extra.update({
            'epoch_date': json.dumps(epoch_date, default=str),
        })
    outgoing_message = OutgoingSMS.objects.create(text=msg,
                                                  extra=extra,
                                                  message_type=OUTGOING_SMS_TYPE.SUBSCRIPTION_NOTIFICATION)

    # send msg
    send_message.delay(outgoing_message.id, list(customers.values_list('id', flat=True)), sender=settings.SMS_SENDER_SUBSCRIPTION)
