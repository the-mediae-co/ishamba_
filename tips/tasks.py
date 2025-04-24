from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template import loader
from django.utils import timezone

import sentry_sdk
from celery import chord
from django_tenants.utils import schema_context

from agri.constants import SUBSCRIPTION_FLAG
from agri.models.base import Commodity
from core.tasks import BaseTask
from core.utils.clients import client_setting, get_all_clients
from customers.models import Customer
from ishamba.celery import app
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS
from sms.tasks import send_message
from tips.models import Tip, TipMessage, TipSeason


@app.task(base=BaseTask)
def send_scheduled_tips(tips_for=None, report_only: bool = False):
    """
    Send all tips that are due to be sent today (or on the date specified)

    Kwargs:
        tips_for: Date specifying which day to send tips for
        report_only: True will just count the messages that would be sent
    """
    global_tips_enabled = client_setting('tips_enabled')
    if not global_tips_enabled:
        return
    task_kwargs = {}
    if settings.ENFORCE_BLACKOUT_HOURS:
        this_hour_local = timezone.localtime(timezone.now()).hour
        if settings.BLACKOUT_END_HOUR <= this_hour_local <= settings.BLACKOUT_BEGIN_HOUR:
            # If we're within the allowed sending hours, send immediately
            pass
        else:
            # delay the sending until the next acceptable hour
            if this_hour_local < settings.BLACKOUT_END_HOUR:
                eta = datetime.now() + timedelta(hours=settings.BLACKOUT_END_HOUR - this_hour_local)
            else:
                eta = datetime.now() + timedelta(hours=(
                    24 - this_hour_local + settings.BLACKOUT_END_HOUR))
            task_kwargs['eta'] = eta
            sentry_sdk.capture_message(f"BLACKOUT: scheduled tip message {tips_for} scheduled "
                                        f"{timezone.localtime(timezone.now())}, delaying until {eta}")

    for client in get_all_clients():
        with schema_context(client.schema_name):

            commodities_with_tips = (Commodity.objects.filter(tips__isnull=False, tips_enabled=True)
                                     .values_list('pk', flat=True)
                                     .distinct())

            for commodity_id in commodities_with_tips:
                args = [client.schema_name, commodity_id]
                kwargs = {
                    'tips_for': tips_for,
                    'report_only': report_only
                }
                if report_only:
                    send_tips_for_commodity(*args, **kwargs)
                else:
                    send_tips_for_commodity.apply_async(args=args, kwargs=kwargs, **task_kwargs)


@app.task(base=BaseTask)
def send_tips_for_commodity(schema_name: str, commodity_id: int, tips_for: str=None, report_only: bool = False):
    """
    Send tips for the given series that are due to be sent today
    (or on the date specified)

    Args:
        series_pk: The series to send tips for...

    Kwargs:
        tips_for: Date specifying which day to send tips for
    """
    with schema_context(schema_name):
        when = tips_for or timezone.now().date()
        tips = Tip.objects.filter(commodity_id=commodity_id, legacy=False)

        if not tips.exists():
            return

        customers = Customer.objects.filter(
            customer_commodities__commodity_id=commodity_id,
            customer_commodities__subscription_flag__in=[SUBSCRIPTION_FLAG.FREEMIUM, SUBSCRIPTION_FLAG.PREMIUM]
        ).distinct()

        for tip_season in TipSeason.objects.filter(commodity_id=commodity_id):
            to_send = list(tips.filter(delay=(when - tip_season.start_date)))
            if not to_send:
                continue

            customer_filters = tip_season.customer_filters or {}
            border3_ids = customer_filters.get('border3', [])
            if not border3_ids:
                continue

            season_customers = customers.filter(border3_id__in=border3_ids)

            for tip in to_send:
                call_center = tip.call_center
                border_query = f'border{call_center.border.level}'
                tip_customers = season_customers.filter(**{border_query: call_center.border_id})

                for tip_translation in tip.translations.all():
                    # FIXME(apryde): Should we not fall back to English if we don't have tips in a customer's preferred language?
                    translation_customers = tip_customers.filter(preferred_language=tip_translation.language)
                    if not translation_customers:
                        continue

                    if report_only:
                        print(tip.id, tip_season.start_date, tip_translation.text, translation_customers.count())
                        continue

                    tip_message = None
                    try:
                        tip_message = TipMessage.objects.get(
                            tip_translation=tip_translation,
                            tip_season=tip_season,
                        )
                    except TipMessage.DoesNotExist:
                        message = OutgoingSMS.objects.create(
                            message_type=OUTGOING_SMS_TYPE.AGRI_TIP,
                            text=tip_translation.text
                        )
                        tip_message = TipMessage.objects.create(
                            tip_translation=tip_translation,
                            tip_season=tip_season,
                            message=message
                        )

                    send_message.delay(
                        tip_message.message.id,
                        recipient_ids=list(translation_customers.values_list('id', flat=True)),
                        sender='iShamba' # TODO(apryde) parameterise this based on call center
                    )


@app.task(base=BaseTask, ignore_result=True)
def send_simulation_report(results, dates):
    values = [cache.get(r) for r in results]
    forecast = list(zip(dates, values))
    ctx = {
        'forecast': forecast,
        'total': sum(values),
    }
    msg = loader.render_to_string('tips/emails/simulation.txt', ctx)
    subject = loader.render_to_string('tips/emails/simulation_subject.txt', ctx)
    send_mail(subject.strip(), msg, settings.DEFAULT_FROM_EMAIL, client_setting('tip_reports_to'))


@app.task(base=BaseTask, ignore_result=True)
def simulate_tip_sending(days=31):
    start = timezone.now().date()
    forecast_dates = []
    tasks = []
    for delta in range(1, days + 1):
        when = start + timedelta(days=delta)
        forecast_dates.append(when)
        tasks.append(send_scheduled_tips.s(tips_for=when, report_only=True))
    chord(tasks)(send_simulation_report.s(forecast_dates))
