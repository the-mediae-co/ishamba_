import datetime

from django.conf import settings
from django.db.models import QuerySet
from django.utils.timezone import now

from celery.utils.log import get_task_logger
from django_tenants.utils import schema_context

from core.tasks import BaseTask
from core.utils.clients import client_setting, get_all_clients
from customers.models import Customer
from digifarm.tasks import send_digifarm_bulk_sms
from ishamba.celery import app
from sms.constants import OUTGOING_SMS_TYPE
from sms.tasks import send_message
from world.models import Border
from sms.models import OutgoingSMS

from .models import CountyForecast


logger = get_task_logger(__name__)


@app.task
def send_weather_forecasts(date=None):
    """
    Sends a weather forecast SMS to premium customers in Kenya.

    Kwargs:
        date: optionally provide a date to select the forecast for
    """
    for client in get_all_clients():
        with schema_context(client.schema_name):
            if client_setting('send_weather'):
                date = date or now().date()

                # Send forecasts for each county
                # TODO: i18n?
                county_ids = Border.kenya_counties.values_list('id', flat=True)
                for county in county_ids:
                    send_forecast_for_county.delay(client.schema_name, county, when=date)


def send_forecast_to_customers(
    schema_name: str,
    county_id: int,
    when: datetime.date,
    forecast: CountyForecast,
    customers: QuerySet | list[Customer],
):
    extra = {
        "county_id": county_id,
        "county_forecast_id": forecast.id,
        "forecast_date": when.isoformat(),
    }
    if forecast.category is not None:
        extra.update(
            {
                "category_name": forecast.category.name,
            }
        )

    sms = OutgoingSMS.objects.create(
        text=forecast.text,
        message_type=OUTGOING_SMS_TYPE.WEATHER_KENMET,
        extra=extra,
    )
    send_message.delay(sms.id, list(customers.values_list('id', flat=True)), sender=settings.SMS_SENDER_KENMET_FORECAST)

    forecast.sent = True
    forecast.save(update_fields=["sent"])


@app.task(base=BaseTask, ignore_result=True)
def send_forecast_for_county(schema_name: str, county_id: int, when: datetime.date = None):
    """
    Send the latest forecast for the given county to a given list of phone_numbers.

    Args:
        client: tenant schema (str)
        county_id: the pk of the county whose forecast should be retrieved
        when: optionally provide a date to select the forecast for
    """
    with schema_context(schema_name):
        when = when or now().date()
        category_customers = None

        # First deal with forecasts for this county that have category restrictions
        category_forecast = (
            CountyForecast.objects.filter(
                sent=False,
                dates__contains=when,
                county_id=county_id,
                category__isnull=False,
            )
            .order_by("id")
            .last()
        )
        customers = Customer.objects.should_receive_messages()
        if category_forecast and category_forecast.premium_only:
            customers = customers.premium()
        customer_ids = set(customers.filter(border1_id=county_id).values_list('id', flat=True))

        if category_forecast:
            category_customers = Customer.objects.filter(
                id__in=customer_ids,
                border1_id=county_id,
                categories=category_forecast.category,
            )
            if category_customers:
                send_forecast_to_customers(
                    schema_name, county_id, when, category_forecast, category_customers
                )

        # look for non-category forecast for county
        forecast = (
            CountyForecast.objects.filter(
                sent=False,
                dates__contains=when,
                county_id=county_id,
                category__isnull=True,
            )
            .order_by("id")
            .last()
        )
        if forecast:
            # Any customers left?
            remaining = customer_ids
            if category_customers:
                remaining = customer_ids.difference(
                    set(category_customers.values_list("id", flat=True))
                )


            if remaining:
                customers = Customer.objects.filter(
                    id__in=remaining, border1_id=county_id
                )
                if forecast.premium_only:
                    customers = customers.premium()
                if customers:
                    send_forecast_to_customers(
                        schema_name, county_id, when, forecast, customers
                )

        # digifarm
        #customers = Customer.objects.digifarm().filter(border1_id=county_id)
        #if forecast.premium_only:
        #    customers = customers.premium()

        #if customers:
         #   send_digifarm_bulk_sms.delay(customers.values_list('digifarm_farmer_id', flat=True), sms_text=forecast.text)
