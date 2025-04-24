import calendar
import csv
import json
import time as perftime
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from logging import getLogger
from time import gmtime, strftime
from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Avg, Count, Sum
from django.db.models.functions import (Coalesce, ExtractIsoWeekDay,
                                        ExtractIsoYear, ExtractWeek, Length)
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import make_aware
from django.views.generic import FormView, TemplateView

import sentry_sdk
from dateutil import parser, rrule
from dateutil.relativedelta import relativedelta

from agri.models.base import Commodity
from callcenters.models import CallCenter
from calls.models import Call
from core import constants
from core.forms import (DateResolutionForm, DateResolutionWithMembershipForm,
                        MetricsForm)
from core.utils.datetime import (localised_date_formatting_string,
                                 localised_time_formatting_string)
from customers.constants import JOIN_METHODS, STOP_METHODS
from customers.models import (CropHistory, Customer, CustomerCategory,
                              NPSResponse)
from interrogation.models import InterrogationSession
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import (DailyOutgoingSMSSummary, IncomingSMS, OutgoingSMS,
                        SMSRecipient)
from tasks.models import Task
from tips.models import TipSeries
from world.models import Border

logger = getLogger(__name__)


OUTGOING_SMS_TYPE_LABELS = dict(OUTGOING_SMS_TYPE.choices)


class HomeTemplateView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context


class ManagementView(TemplateView):
    template_name = 'management/management_base.html'


def new_customers_chart(request):
    labels = []
    data = []

    if 'endDate' in request.GET:
        unaware_end = parser.parse(request.GET['endDate'])
    else:
        unaware_end = datetime.today()
    aware_end = make_aware(unaware_end) + timedelta(days=1)  # (add one day to make it an inclusive range)

    if 'startDate' in request.GET:
        unaware_start = parser.parse(request.GET['startDate'])
    else:
        unaware_start = unaware_end - timedelta(weeks=2)
    aware_start = make_aware(unaware_start)

    call_center = None
    if 'call_center' in request.GET:
        call_center = CallCenter.objects.get(pk=request.GET['call_center'])

    # If the search range is less than 4 weeks, plot daily statistics, otherwise weekly.
    plot_weekly = aware_end - aware_start > timedelta(days=28)

    queryset = Customer.objects.all()
    if call_center:
        queryset = Customer.objects.filter(**{f'border{call_center.border.level}': call_center.border_id})

    queryset = (queryset.filter(created__range=[aware_start, aware_end])
                .annotate(day=ExtractIsoWeekDay('created'),
                          week=ExtractWeek('created'),
                          year=ExtractIsoYear('created')))

    if plot_weekly:
        queryset = queryset.values('year', 'week').annotate(count=Count('week')).order_by('year', 'week')
    else:
        queryset = queryset.values('year', 'week', 'day').annotate(count=Count('day')).order_by('year', 'week', 'day')

    for record in queryset:
        # If plot_weekly, the day for the label is always Monday
        day = 1 if plot_weekly else record['day']
        week_str = str(record['year']) + '-' + str(record['week']) + '-' + str(day)
        date_str = str(datetime.strptime(week_str, '%G-%V-%u').date())
        labels.append(date_str)
        data.append(record['count'])

    return JsonResponse(data={
        'labels': labels,
        'data': data,
    })


def task_metrics_chart(request):
    labels = []
    new_tasks = []
    resolved_tasks = []
    new_weeks = {}
    resolved_weeks = {}

    if 'endDate' in request.GET:
        unaware_end = parser.parse(request.GET['endDate'])
    else:
        unaware_end = datetime.today()
    aware_end = make_aware(unaware_end) + timedelta(days=1)  # (add one day to make it an inclusive range)

    if 'startDate' in request.GET:
        unaware_start = parser.parse(request.GET['startDate'])
    else:
        unaware_start = unaware_end - timedelta(weeks=2)
    aware_start = make_aware(unaware_start)

    call_center = None
    if 'call_center' in request.GET:
        call_center = CallCenter.objects.get(pk=request.GET['call_center'])

    # If the search range is less than 4 weeks, plot daily statistics, otherwise weekly.
    plot_weekly = aware_end - aware_start > timedelta(days=28)

    new_tasks_query = Task.objects.filter(created__range=[aware_start, aware_end])

    if call_center:
        new_tasks_query = new_tasks_query.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})

    new_tasks_query = new_tasks_query.annotate(day=ExtractIsoWeekDay('created'),
                                               week=ExtractWeek('created'),
                                               year=ExtractIsoYear('created'))

    if plot_weekly:
        new_tasks_query = new_tasks_query.values('year', 'week').annotate(count=Count('week')).order_by('year', 'week')
    else:
        new_tasks_query = new_tasks_query.values('year', 'week', 'day').annotate(count=Count('day')).order_by('year', 'week', 'day')

    # Restructure data set as pseudo-array with week as key
    for record in new_tasks_query:
        key_str = f"{record['year']}-{record['week']:02}-1" if plot_weekly else f"{record['year']}-{record['week']:02}-{record['day']}"
        new_weeks[key_str] = record['count']

    # Find tasks resolved within the past year, annotating by 'last_updated' week number
    resolved_tasks_query = (Task.objects.filter(last_updated__range=[aware_start, aware_end])
                            .exclude(status=Task.STATUS.new)
                            .exclude(status=Task.STATUS.progressing))

    if call_center:
        resolved_tasks_query = resolved_tasks_query.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})

    resolved_tasks_query = resolved_tasks_query.annotate(day=ExtractIsoWeekDay('last_updated'),
                                                         week=ExtractWeek('last_updated'),
                                                         year=ExtractIsoYear('last_updated'))

    if plot_weekly:
        resolved_tasks_query = resolved_tasks_query.values('year', 'week').annotate(count=Count('week')).order_by('year', 'week')
    else:
        resolved_tasks_query = resolved_tasks_query.values('year', 'week', 'day').annotate(count=Count('day')).order_by('year', 'week', 'day')

    # Restructure data set as pseudo-array with week as key
    for record in resolved_tasks_query:
        key_str = f"{record['year']}-{record['week']:02}-1" if plot_weekly else f"{record['year']}-{record['week']:02}-{record['day']}"
        resolved_weeks[key_str] = record['count']

    # Combine key sets
    keys = sorted(set(list(new_weeks.keys()) + list(resolved_weeks.keys())))

    # Now walk the data sets and create the graph data points
    for key in keys:
        date_str = str(datetime.strptime(key, '%G-%V-%u').date())
        labels.append(date_str)
        try:
            new_tasks.append(new_weeks[key])
        except KeyError:
            new_tasks.append(0)

        try:
            resolved_tasks.append(resolved_weeks[key])
        except KeyError:
            resolved_tasks.append(0)

    return JsonResponse(data={
        'labels': labels,
        'data': [new_tasks, resolved_tasks],
    })


def get_metrics(start_date, end_date, call_center: Optional[CallCenter] = None):
    logger.debug("Generating metrics for %s", call_center)
    tic = perftime.perf_counter()

    # We're submitting dates in the form, but in most objects of interest the
    # pertinent field is a datetime field, so we convert to aware_start and
    # aware_end.
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    unaware_start = datetime.combine(start_date, time.min)
    aware_start = make_aware(unaware_start)
    unaware_end = datetime.combine(end_date, time.max)
    aware_end = make_aware(unaware_end)

    # Customers
    customers = Customer.objects.all()
    if call_center:
        customers = customers.filter(**{f'border{call_center.border.level}': call_center.border_id})

    total_customers = customers.count()
    # Digifarm farmers had their phone set to '+492'
    df_only_customers = customers.filter(digifarm_farmer_id__isnull=False)\
        .exclude(phones__number__startswith='+2').count()
    stopped_non_df_customers = customers.filter(has_requested_stop=True)\
        .filter(phones__number__startswith='+2').count()
    premium_customers = customers.premium().count()
    new_customers = customers.filter(created__range=[aware_start, aware_end]).count()
    updated_customers = customers.filter(last_updated__range=[aware_start, aware_end]).count()
    join_methods = customers.filter(created__range=[aware_start, aware_end])\
        .order_by('join_method').values('join_method').annotate(count=Count('join_method')).values('join_method',
                                                                                                   'count')
    stop_methods = customers.filter(has_requested_stop=True, last_updated__range=[aware_start, aware_end])\
        .order_by('stop_method').values('stop_method').annotate(count=Count('stop_method')).values('stop_method',
                                                                                                   'count')
    # Combine '' into the 'unknown' key
    join_method_counts = {}
    for item in join_methods:
        method = item['join_method'] or '?'  # empty strings get turned into unknown method
        if method in join_method_counts:
            join_method_counts[method] += item['count']
        else:
            join_method_counts[method] = item['count']

    stop_method_counts = {}
    for item in stop_methods:
        method = item['stop_method'] or '?'  # empty strings get turned into unknown method
        if method in stop_method_counts:
            stop_method_counts[method] += item['count']
        else:
            stop_method_counts[method] = item['count']

    toc1 = perftime.perf_counter()

    # USSD Registrations
    # NOTE: USSD is only enabled in Kenya.
    ussd_start_count = 0
    ussd_success_count = 0
    if not call_center or call_center.border.country == "Kenya":
        ussd_start_count = InterrogationSession.objects.filter(created__range=[aware_start, aware_end]).count()
        ussd_success_count = InterrogationSession.objects.filter(created__range=[aware_start, aware_end],
                                                                 finished=True).count()


    # Received SMS
    incoming_sms = IncomingSMS.objects.filter(at__range=[aware_start, aware_end])
    if call_center:
        incoming_sms = incoming_sms.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})

    received_sms_count = incoming_sms.count()
    toc2 = perftime.perf_counter()

    # Tasks
    tasks_created = Task.objects.filter(created__range=[aware_start, aware_end])
    if call_center:
        tasks_created = tasks_created.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})


    task_created_count = tasks_created.count()

    closed_tasks = (tasks_created
                    .exclude(status=Task.STATUS.new)
                    .exclude(status=Task.STATUS.progressing))
    task_closed_count = closed_tasks.count()

    cco_resolved_tasks = []
    task_sum = 0
    task_cco_ids = closed_tasks.values_list('last_editor_id', flat=True).distinct()
    for cco in get_user_model().objects.filter(id__in=task_cco_ids):
        cco_tasks = closed_tasks.filter(last_editor_id=cco.id)
        count = cco_tasks.count()
        cco_resolved_tasks.append({
            'cco': cco.username,
            'count': count,
        })
        task_sum += count
    if task_sum < task_closed_count:
        cco_resolved_tasks.append({
            'cco': 'unknown',
            'count': task_closed_count - task_sum,
        })
    toc3 = perftime.perf_counter()

    # Received calls
    cco_received_calls = []
    received_calls = Call.objects.filter(created_on__range=[aware_start, aware_end]).order_by('cco')
    if call_center:
        received_calls = received_calls.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})

    avg_duration = received_calls.aggregate(Avg('duration'))['duration__avg'] or 0
    total_duration = received_calls.aggregate(Sum('duration'))['duration__sum'] or 0
    total_received_count = received_calls.count()
    all_received_calls = {
        'count': total_received_count,
        'avg_duration': avg_duration if avg_duration else 0,
        'total_duration': total_duration if total_duration else 0,
    }
    ccos = received_calls.values_list('cco', flat=True).distinct()
    duration_sum = 0
    count_sum = 0
    for cco in get_user_model().objects.filter(id__in=ccos):
        cco_calls = received_calls.filter(cco=cco.id)
        duration = cco_calls.aggregate(Sum('duration'))['duration__sum']
        duration = duration if duration else 0
        avg_duration = cco_calls.aggregate(Avg('duration'))['duration__avg']
        avg_duration = avg_duration if avg_duration else 0
        count = cco_calls.count()
        cco_received_calls.append({
            'cco': cco.username,
            'count': count,
            'avg_duration': avg_duration,
            'total_duration': duration,
        })
        duration_sum += duration
        count_sum += count

    if duration_sum < total_duration or count_sum < total_received_count:
        duration = total_duration - duration_sum
        count = total_received_count - count_sum
        if count > 0:
            avg_duration = duration / count
        else:
            avg_duration = 0
        cco_received_calls.append({
            'cco': 'Unknown (unanswered?)',
            'count': count,
            'avg_duration': avg_duration,
            'total_duration': duration,
        })
    toc4 = perftime.perf_counter()

    # Sent SMS - Estimate based on postgresql analyze tables
    # with connection.cursor() as cursor:
    #     cursor.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = 'ishamba.sms_smsrecipient'::regclass;")
    #     values = cursor.fetchall()
    #     sent_sms_count = values[0][0]
    country_id = Border.objects.get(name="Kenya", level=0).pk
    if call_center:
        country_id = Border.objects.get(name=call_center.border.country, level=0).pk
    query = DailyOutgoingSMSSummary.objects.filter(date__range=[aware_start, aware_end], country_id=country_id)
    if query:
        sent_sms_count_dict = query.aggregate(Sum('count'), Sum('cost'))
        sent_sms_count = sent_sms_count_dict.get('count__sum', 0)
        sent_sms_cost = str(sent_sms_count_dict.get('cost__sum', 0))
        sent_sms_cost_units = query.first().cost_units
    else:
        sent_sms_count = 0
        sent_sms_cost = '0.00'
        sent_sms_cost_units = 'kes'
    toc5 = perftime.perf_counter()

    sms_type_counts = {}
    sms_type_costs = {}
    sms_type_cost_units = {}
    message_types = DailyOutgoingSMSSummary.objects.filter(
            date__range=[aware_start, aware_end], country_id=country_id)\
        .order_by('message_type')\
        .distinct('message_type')\
        .only('message_type')\
        .values_list('message_type', flat=True)
    for message_type in message_types:
        query = DailyOutgoingSMSSummary.objects.filter(
            date__range=[aware_start, aware_end],
            country_id=country_id,
            message_type=message_type,
        )
        count_dict = query.aggregate(Sum('count'), Sum('cost'))
        sms_type_counts[message_type] = count_dict.get('count__sum', 0)
        sms_type_costs[message_type] = str(count_dict.get('cost__sum', 0))
        # We make the assumption that messages in the same country use the same cost units.
        sms_type_cost_units[message_type] = query.first().cost_units

    toc6 = perftime.perf_counter()

    # Crop Histories
    crop_histories = CropHistory.objects.all()
    if call_center:
        crop_histories = crop_histories.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})


    crop_history_count = crop_histories.filter(created__range=[aware_start, aware_end]).count()
    crop_history_updated_count = crop_histories.filter(last_updated__range=[aware_start, aware_end]).count()

    # FIXME(apryde): TipSeries isn't a thing anymore. Remove temporarily and
    # reinstante once Kaan's subscription work lands?
    # TipSeriesSubscriptions
    tips = (
        TipSeries.objects
        .annotate(num_subscribers=Count("subscriptions"))
        .filter(num_subscribers__gt=0)
    )

    # Commodities and subscribers
    commodities = Commodity.objects.all()
    if call_center:
        commodities = commodities.filter(**{f'customers__border{call_center.border.level}': call_center.border_id})
    commodities = commodities.annotate(num_subscribers=Count('customers')).filter(num_subscribers__gt=0)
    toc7 = perftime.perf_counter()

    # Customer activity metrics
    customer_active_score = {}
    active_customer_calls_qs = (Call.objects.filter(created_on__range=[aware_start, aware_end])
                                .values('customer_id')
                                .annotate(count=Count('customer_id'),
                                          duration=Coalesce(Sum('duration'), 0)))
    if call_center:
        active_customer_calls_qs = active_customer_calls_qs.filter(**{f'customer__border{call_center.border.level}': call_center.border_id})
    active_customer_calls = active_customer_calls_qs.values_list('customer_id', 'count', 'duration')

    # Collect the top-10 IDs by each metric. Start by creating dicts for
    # each customer that's in the top-10 of each metric.
    for customer_id, count, duration in active_customer_calls.values_list('customer_id', 'count', 'duration'):
        customer_active_score[customer_id] = {
            'customer_id': customer_id,
            'call_count': count,
            'call_duration': duration,
            'sms_count': 0
        }

    active_customer_sms_by_count = (incoming_sms
                                    .exclude(text__iregex=r'^\s*stop')  # Filter out incoming STOP messages
                                    .annotate(text_len=Length('text'))  # Filter out messages less than 2 chars in length
                                    .filter(text_len__gt=1)
                                    .values('customer_id')
                                    .annotate(count=Count('customer_id'))
                                    .order_by('-count'))

    for customer_id, count in active_customer_sms_by_count.values_list('customer_id', 'count'):
        if count == 0:
            # These are sorted by count descending so once we reach zero count, break the loop
            break
        if customer_id in customer_active_score:
            # If this id exists in the dict, then the call stats must have been entered above, so just add the sms stats
            customer_active_score[customer_id].update({'sms_count': count})
        else:
            # If their call stats were not entered, set them to zero
            customer_active_score[customer_id] = {
                'customer_id': customer_id,
                'call_count': 0,
                'call_duration': 0,
                'sms_count': count,
            }

    # Remove mediae and ishamba customers
    try:
        mediae_ids = CustomerCategory.objects.get(name="Mediae Staff").customer_set.values_list('id', flat=True)
        for id in mediae_ids:
            customer_active_score.pop(id, None)  # Remove the employee from the active customers
    except CustomerCategory.DoesNotExist as e:
        sentry_sdk.capture_message(f"CustomerCategory named 'Mediae Staff' not found")

    try:
        ishamba_ids = CustomerCategory.objects.get(name="iShamba Team").customer_set.values_list('id', flat=True)
        for id in ishamba_ids:
            customer_active_score.pop(id, None)  # Remove the employee from the active customers
    except CustomerCategory.DoesNotExist as e:
        sentry_sdk.capture_message(f"CustomerCategory named 'iShamba Team' not found")

    # Premium customers get a score boost
    premium_ids = customers.premium().values_list('id', flat=True)

    # Now loop through all top-100 customers to calculate a total score
    for id in customer_active_score.keys():
        score = customer_active_score[id].get('sms_count', 0) * 10
        score += customer_active_score[id].get('call_count', 0) * 10
        score += round(customer_active_score[id].get('call_duration', 0) / 60)
        if id in premium_ids:
            score += 20
        customer_active_score[id].update({'score': score})

    # Sort the dict keys by score, largest to smallest
    sorted_score_ids = sorted(customer_active_score,
                              key=lambda d: customer_active_score[d]['score'],
                              reverse=True)

    sorted_customer_scores = [customer_active_score[x] for x in sorted_score_ids[:100]]

    toc8 = perftime.perf_counter()

    logger.debug(f"METRICS_TIMING: t1={(toc1-tic):0.2f}, t2={(toc2-toc1):0.2f}, t3={(toc3-toc2):0.2f}, "
                 f"t4={(toc4-toc3):0.2f}, t5={(toc5-toc4):0.2f}, "
                 f"t6={(toc6-toc5):0.2f}, t7={(toc7-toc6):0.2f}, t8={(toc8-toc7):0.2f}")
    return {
        'start_date': aware_start.date,
        'end_date': aware_end.date,
        'total_customers': total_customers,
        'df_only_customers': df_only_customers,
        'premium_customers': premium_customers,
        'stopped_non_df_customers': stopped_non_df_customers,
        'new_customers': new_customers,
        'updated_customers': updated_customers,
        'join_method_counts': join_method_counts,
        'stop_method_counts': stop_method_counts,
        'sorted_customer_scores': sorted_customer_scores,
        'ussd_start_count': ussd_start_count,
        'ussd_success_count': ussd_success_count,
        'received_sms_count': received_sms_count,
        'all_received_calls': all_received_calls,
        'task_created_count': task_created_count,
        'task_closed_count': task_closed_count,
        'cco_resolved_tasks': cco_resolved_tasks,
        'cco_received_calls': cco_received_calls,
        'sent_sms_count': sent_sms_count,
        'sent_sms_cost': sent_sms_cost,
        'sent_sms_cost_units': sent_sms_cost_units,
        'sms_type_counts': sms_type_counts,
        'sms_type_costs': sms_type_costs,
        'sms_type_cost_units': sms_type_cost_units,
        'tips': tips,
        'crop_history_count': crop_history_count,
        'crop_history_updated_count': crop_history_updated_count,
        'commodities': commodities,
    }


class MetricsView(FormView):
    template_name = 'management/metrics.html'
    form_class = MetricsForm
    success_url = 'core_management_metrics'

    def get_initial(self):
        start_weekday = 0  # Monday
        end_date = make_aware(datetime.now()).date()
        start_date = end_date + relativedelta(weeks=-2, weekday=start_weekday)

        initial = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        }

        call_center = CallCenter.objects.for_operator(self.request.user)
        if call_center:
            initial['call_center'] = call_center

        return initial

    def get_form_kwargs(self):
        kwargs = {
            'initial': self.get_initial(),
            'prefix': self.get_prefix()
        }
        if any(x in self.request.GET for x in ['submit', 'export']):
            # If a button generated this request, attach the data to kwargs
            kwargs.update({
                'data': self.request.GET,
            })
        return kwargs

    def export_metrics_csv(self, start_date: str, end_date: str, metrics: dict):
        # Create the HttpResponse object with the appropriate CSV header.
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="exported_metrics.csv"'},
        )

        # Get the localized strftime format string
        format_string = localised_time_formatting_string()

        writer = csv.writer(response)
        writer.writerow(['Date range', start_date, end_date])
        writer.writerow(['---------- CUSTOMERS ----------'])
        writer.writerow(['Total Customers (now)', metrics.get('total_customers')])
        writer.writerow(['Digifarm-only Customers (now)', metrics.get('df_only_customers')])
        writer.writerow(['Premium Customers (now)', metrics.get('premium_customers')])
        writer.writerow(['Stopped non-DF Customers (now)', metrics.get('stopped_non_df_customers')])
        writer.writerow([f'New Customers ({start_date} to {end_date})', metrics.get('new_customers')])
        writer.writerow([f'Updated Customers ({start_date} to {end_date})', metrics.get('updated_customers')])
        writer.writerow([f'Customer Join Methods ({start_date} to {end_date})'])
        writer.writerow(['', 'Method', 'Count'])
        for k, v in metrics.get('join_method_counts').items():
            writer.writerow(['',  dict(JOIN_METHODS.choices).get(k).title(), v])
        writer.writerow([f'Customer Stop Methods ({start_date} to {end_date})'])
        writer.writerow(['', 'Method', 'Count'])
        for k, v in metrics.get('stop_method_counts').items():
            writer.writerow(['', dict(STOP_METHODS.choices).get(k).title(), v])
        writer.writerow([f'Top-100 Active Customers ({start_date} to {end_date})',
                         '10 points per SMS + 10 points per call + 1 point per minute of call + 20 points if Premium subscriber'])
        writer.writerow(['', 'Customer ID', 'Score', 'SMS Count', 'Call Count', 'Call Duration'])
        for c in metrics.get('sorted_customer_scores'):
            writer.writerow(['', c.get('customer_id'), c.get('score'), c.get('sms_count'),
                             c.get('call_count'), strftime(format_string, gmtime(c.get('call_duration')))])

        writer.writerow([f'---------- USSD ({start_date} to {end_date}) ----------'])
        writer.writerow(['USSD Sessions Started', metrics.get('ussd_start_count')])
        writer.writerow(['USSD Sessions Completed', metrics.get('ussd_success_count')])

        writer.writerow([f'---------- CALLS ({start_date} to {end_date}) ----------'])
        writer.writerow(['Received Call Count', metrics.get('all_received_calls').get('count')])
        avg_call_duration = metrics.get('all_received_calls').get('avg_duration')
        writer.writerow(['Average Call Duration', strftime(format_string, gmtime(avg_call_duration))])
        total_call_duration = metrics.get('all_received_calls').get('total_duration')
        writer.writerow(['Total Call Duration', strftime(format_string, gmtime(total_call_duration))])
        cco_call_stats = metrics.get('cco_received_calls')
        if cco_call_stats:
            writer.writerow(['Received Calls per CCO', 'Username', 'Count', 'Average Duration', 'Total Duration'])
            for cco_dict in cco_call_stats:
                cco = cco_dict.get('cco')
                if isinstance(cco, User):
                    username = cco.username
                else:
                    username = cco
                writer.writerow(['',
                                 username,
                                 cco_dict.get('count'),
                                 strftime(format_string, gmtime(cco_dict.get('avg_duration'))),
                                 strftime(format_string, gmtime(cco_dict.get('total_duration'))),
                                 ])

        writer.writerow([f'---------- TASKS ({start_date} to {end_date}) ----------'])
        writer.writerow(['Tasks Created', metrics.get('task_created_count')])
        writer.writerow(['Tasks Closed', metrics.get('task_closed_count')])
        cco_task_stats = metrics.get('cco_resolved_tasks')
        if cco_task_stats:
            writer.writerow(['Tasks Closed per CCO', 'Username', 'Count'])
            for cco_dict in cco_task_stats:
                cco = cco_dict.get('cco')
                if isinstance(cco, User):
                    username = cco.username
                else:
                    username = cco
                writer.writerow(['', username, cco_dict.get('count')])

        writer.writerow([f'---------- SMS ({start_date} to {end_date}) ----------'])
        writer.writerow(['Received SMS Count', metrics.get('received_sms_count')])
        writer.writerow(['Sent SMS Count', metrics.get('sent_sms_count')])
        writer.writerow(['Sent SMS Cost', metrics.get('sent_sms_cost'), metrics.get('sent_sms_cost_units')])
        sms_type_counts = metrics.get('sms_type_counts')
        sms_type_costs = metrics.get('sms_type_costs')
        sms_type_cost_units = metrics.get('sms_type_cost_units')
        if sms_type_counts and sms_type_costs:
            writer.writerow(['SMS Type Stats', 'Type', 'Count', 'Cost', 'Units'])
            for sms_type in sms_type_counts.keys():
                writer.writerow(['', OUTGOING_SMS_TYPE_LABELS.get(sms_type, sms_type), sms_type_counts.get(sms_type),
                                 sms_type_costs.get(sms_type), sms_type_cost_units.get(sms_type)])

        writer.writerow([f'---------- CROP HISTORIES ({start_date} to {end_date}) ----------'])
        writer.writerow(['Crop History Count', metrics.get('crop_history_count')])
        writer.writerow(['Crop History Updated Count', metrics.get('crop_history_updated_count')])

        writer.writerow(['---------- COMMODITIES (now) ----------'])
        commodities = metrics.get('commodities').order_by('-num_subscribers')
        for c in commodities:
            if c.num_subscribers > 0:
                writer.writerow(['', c.name, c.num_subscribers])

        return response

    def get(self, request, *args, **kwargs):
        """ Mimic self.post
        """
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_bound:
            if form.is_valid():
                return self.form_valid(form)
        # Page is just a plain GET with no submit. Get default metrics range.
        context = self.get_context_data(form=form)
        call_center = CallCenter.objects.for_operator(self.request.user)
        if call_center:
            context.update({'call_center': call_center})
        metrics = get_metrics(form.initial['start_date'], form.initial['end_date'], call_center=call_center)
        context.update({
            'metrics': metrics,
        })
        if self.request.GET.get('export'):
            return self.export_metrics_csv(form.initial['start_date'], form.initial['end_date'], metrics)
        else:
            return self.render_to_response(context)

    def form_valid(self, form):
        # If the form's date range was changed...
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        call_center = form.cleaned_data['call_center']
        context = self.get_context_data(form=form)
        metrics = get_metrics(start_date, end_date, call_center=call_center)
        if call_center:
            context.update({'call_center': call_center})
        context.update({
            'metrics': metrics,
        })
        if self.request.GET.get('export'):
            return self.export_metrics_csv(form.initial['start_date'], form.initial['end_date'], metrics)
        else:
            return self.render_to_response(context)

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #
    #     return context


class BaseChartView(TemplateView):
    form_class = DateResolutionForm
    template_name = 'management/chart.html'
    stacked = False

    def get_initial_dates(self):
        date_resolution = constants.DATE_RESOLUTION_MONTHS
        start_date = make_aware(datetime.now()).date() + relativedelta(day=1, months=-4)
        end_date = make_aware(datetime.now()).date()

        return start_date, end_date, date_resolution

    def get_initial(self):
        start_date, end_date, date_resolution = self.get_initial_dates()

        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'date_resolution': date_resolution,
        }

    def get_form_kwargs(self):
        kwargs = {
            'initial': self.get_initial(),
        }
        kwargs.update({
            'data': self.request.GET,
        })
        return kwargs

    def get_form_class(self):
        return self.form_class

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(**self.get_form_kwargs())

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_bound:
            if form.is_valid():
                return self.form_valid(form)
        # Page is just a plain GET with no submit. Get default chart data.
        context = self.get_context_data(form=form)
        context.update({
            'chartdata': json.dumps(self.get_chart_data(*self.get_initial_dates()))
        })
        return self.render_to_response(context)

    def form_valid(self, form):
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        date_resolution = form.cleaned_data['date_resolution']
        include_inactive = form.cleaned_data.get('include_inactive_customers', False)
        context = self.get_context_data(form=form)
        context.update({
            'chartdata': json.dumps(self.get_chart_data(
                start_date, end_date, date_resolution,
                include_inactive=include_inactive,
            )),
        })
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        if 'view' not in kwargs:
            kwargs['view'] = self
        return kwargs

    def get_chart_data(self, start_date, end_date, date_resolution,
                       include_inactive=False):
        rrule_daysets = {
            constants.DATE_RESOLUTION_DAYS: rrule.DAILY,
            constants.DATE_RESOLUTION_WEEKS: rrule.WEEKLY,
            constants.DATE_RESOLUTION_MONTHS: rrule.MONTHLY,
        }

        # Get the localized strftime format string
        format_string = localised_date_formatting_string()

        date_string_format = {
            constants.DATE_RESOLUTION_DAYS: format_string,
            constants.DATE_RESOLUTION_WEEKS: format_string,
            constants.DATE_RESOLUTION_MONTHS: "%d %B",
        }[date_resolution]

        dates = rrule.rrule(rrule_daysets[date_resolution], start_date, until=end_date)

        columns = []

        rd = relativedelta(**{date_resolution: 1})
        results = self.get_objects_for_dates(dates, rd, include_inactive)

        for k, v in results.items():
            if isinstance(k, date):
                k = k.strftime(date_string_format)
            column = [k]
            for result in v:
                column.append(result)
            columns.append(column)

        if self.stacked is False:
            groups = []
        else:
            groups = [[c[0] for c in columns]]

        return {
            'columns': columns,
            'groups': groups,
            'dates': [d.strftime(date_string_format) for d in dates],
        }


class MembershipRateChartView(BaseChartView):
    form_class = DateResolutionWithMembershipForm

    def get_objects_for_dates(self, dates, rd, include_inactive):
        results = defaultdict(list)
        for d in dates:
            custs = Customer.objects.filter(date_registered__gt=d, date_registered__lte=d + rd)
            if include_inactive is False:
                custs = custs.should_receive_messages()
            results['Membership'].append(
                custs.count()
            )
        return results


class CallRateChartView(BaseChartView):

    def get_objects_for_dates(self, dates, rd, include_inactive):
        results = defaultdict(list)
        for d in dates:
            calls = Call.objects.filter(created_on__gt=d, created_on__lte=d + rd)
            results['Successful Inbound'].append(
                calls.filter(direction__iexact='inbound').exclude(connected_on=None).count()
            )
            results['Unsuccessful Inbound'].append(
                calls.filter(direction__iexact='inbound', connected_on=None).count()
            )
        return results


def nps_histogram_chart(request):
    t1 = perftime.perf_counter()
    today = datetime.now()
    last_day = calendar.monthrange(today.year, today.month)[1]
    this_month_begin = make_aware(datetime(today.year, today.month, 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    this_month_end = make_aware(datetime(today.year, today.month, last_day)).replace(hour=0, minute=0, second=0, microsecond=0)
    last_month_end = (this_month_begin - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    last_month_begin = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    t2 = perftime.perf_counter()
    if request.method == 'POST':
        score = int(request.POST.get('binIndex'))
        dataset_index = int(request.POST.get('datasetIndex'))
        # Total, Last month, This month
        if dataset_index == 0:
            customers = list(NPSResponse.objects.filter(score=score)
                             .values('customer__id',
                                     'customer__sex',
                                     'customer__name',
                                     'customer__border3',  # receives PV weather forecasts
                                     'customer__border0__name',
                                     'customer__border1__name',
                                     )
                             )
        else:
            dataset_beginnings = [last_month_begin, this_month_begin]
            dataset_endings = [last_month_end, this_month_end]
            customers = list(NPSResponse.objects.filter(score=score,
                                                        created__range=[dataset_beginnings[dataset_index - 1],
                                                                        dataset_endings[dataset_index - 1]])
                             .values('customer__id',
                                     'customer__sex',
                                     'customer__name',
                                     'customer__border3',  # receives PV weather forecasts
                                     'customer__border0__name',
                                     'customer__border1__name',
                                     )
                             )

        return JsonResponse(data={
            'selected_customers': customers,
        })

    # else
    nps_chart_total_count = NPSResponse.objects.count()
    nps_chart_total_labels = list(range(11))
    nps_chart_total_counts = [0] * 11
    nps_chart_total_pcts = [0] * 11
    t3 = perftime.perf_counter()
    with connection.cursor() as cursor:
        sql = f"select width_bucket(score, array[0,1,2,3,4,5,6,7,8,9,10]) as bucket, count(*) " \
              f"from ishamba.customers_npsresponse " \
              f"group by bucket order by bucket;"
        cursor.execute(sql, )
        data = cursor.fetchall()
        for row in data:
            # Bucket indices are one-based
            nps_chart_total_counts[row[0] - 1] = row[1]
            nps_chart_total_pcts[row[0] - 1] = 100 * (row[1] / nps_chart_total_count)
    t4 = perftime.perf_counter()
    nps_chart_this_month_count = NPSResponse.objects.filter(created__range=[this_month_begin, this_month_end]).count()
    nps_chart_this_month_labels = list(range(11))
    nps_chart_this_month_counts = [0] * 11
    nps_chart_this_month_pcts = [0] * 11
    t5 = perftime.perf_counter()
    with connection.cursor() as cursor:
        sql = f"select width_bucket(score, array[0,1,2,3,4,5,6,7,8,9,10]) as bucket, count(*) " \
              f"from ishamba.customers_npsresponse where created between '{this_month_begin.isoformat()}' AND '{this_month_end.isoformat()}' " \
              f"group by bucket order by bucket;"
        cursor.execute(sql, )
        data = cursor.fetchall()
        for row in data:
            # Bucket indices are one-based
            nps_chart_this_month_counts[row[0] - 1] = row[1]
            nps_chart_this_month_pcts[row[0] - 1] = 100 * (row[1] / nps_chart_this_month_count)
    t6 = perftime.perf_counter()
    nps_chart_last_month_count = NPSResponse.objects.filter(created__range=[last_month_begin, last_month_end]).count()
    nps_chart_last_month_labels = list(range(11))
    nps_chart_last_month_counts = [0] * 11
    nps_chart_last_month_pcts = [0] * 11
    t7 = perftime.perf_counter()
    with connection.cursor() as cursor:
        sql = f"select width_bucket(score, array[0,1,2,3,4,5,6,7,8,9,10]) as bucket, count(*) " \
              f"from ishamba.customers_npsresponse where created between '{last_month_begin.isoformat()}' AND '{last_month_end.isoformat()}' " \
              f"group by bucket order by bucket;"
        cursor.execute(sql, )
        data = cursor.fetchall()
        for row in data:
            # Bucket indices are one-based
            nps_chart_last_month_counts[row[0] - 1] = row[1]
            nps_chart_last_month_pcts[row[0] - 1] = 100 * (row[1] / nps_chart_last_month_count)
    t8 = perftime.perf_counter()
    logger.debug(
        f"nps_histogram_chart: t2: {t2 - t1:0.1f}, t3: {t3 - t2:0.1f}, t4: {t4 - t3:0.1f}, t5: {t5 - t4:0.1f}, t6: {t6 - t5:0.1f}, t7: {t7 - t6:0.1f}, t8: {t8 - t7:0.1f}"
    )

    return JsonResponse(data={
        'nps_chart_total_count': nps_chart_total_count,
        'nps_chart_total_labels': nps_chart_total_labels,
        'nps_chart_total_counts': nps_chart_total_counts,
        'nps_chart_total_pcts': nps_chart_total_pcts,
        'nps_chart_this_month_count': nps_chart_this_month_count,
        'nps_chart_this_month_labels': nps_chart_this_month_labels,
        'nps_chart_this_month_counts': nps_chart_this_month_counts,
        'nps_chart_this_month_pcts': nps_chart_this_month_pcts,
        'nps_chart_last_month_count': nps_chart_last_month_count,
        'nps_chart_last_month_labels': nps_chart_last_month_labels,
        'nps_chart_last_month_counts': nps_chart_last_month_counts,
        'nps_chart_last_month_pcts': nps_chart_last_month_pcts,
    })


class NPSView(ManagementView):
    template_name = 'management/nps.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        t1 = perftime.perf_counter()
        nps_total_count = NPSResponse.objects.count()

        # Although one would think that the following sequence of extracting IDs separately
        # would not be necessary, it makes more than a 2 minute difference in query performance.
        request_ids = list(OutgoingSMS.objects.filter(message_type=OUTGOING_SMS_TYPE.NPS_REQUEST).values_list('id', flat=True))
        nps_sent_total_count = SMSRecipient.objects.filter(message_id__in=request_ids, page_index=1).count()

        nps_total_response_rate = 100 * (nps_total_count / nps_sent_total_count)

        t2 = perftime.perf_counter()
        nps_total_histogram = [['Detractors (0-6)', 0, 0], ['Passives (7-8)', 0, 0], ['Promoters (9-10)', 0, 0]]
        with connection.cursor() as cursor:
            sql = "select width_bucket(score, array[0,7,9]) as bucket, count(*) " \
                  "from ishamba.customers_npsresponse group by bucket order by bucket;"
            cursor.execute(sql, )
            data = cursor.fetchall()
            for row in data:
                nps_total_histogram[row[0] - 1][1] = row[1]  # count
                nps_total_histogram[row[0] - 1][2] = 100 * (row[1] / nps_total_count)  # pct

        t3 = perftime.perf_counter()
        pv_npsresponse_ids = list(NPSResponse.objects.filter(customer__border3__isnull=False).values_list('id', flat=True))
        pv_total_count = len(pv_npsresponse_ids)
        t4 = perftime.perf_counter()
        pv_histogram = [['Detractors (0-6)', 0, 0], ['Passives (7-8)', 0, 0], ['Promoters (9-10)', 0, 0]]
        with connection.cursor() as cursor:
            sql = f"select width_bucket(score, array[0,7,9]) as bucket, count(*) " \
                  f"from ishamba.customers_npsresponse " \
                  f"where customers_npsresponse.id IN ({','.join(map(str, pv_npsresponse_ids))}) " \
                  f"group by bucket order by bucket;"
            cursor.execute(sql, )
            data = cursor.fetchall()
            for row in data:
                pv_histogram[row[0] - 1][1] = row[1]  # count
                pv_histogram[row[0] - 1][2] = 100 * (row[1] / pv_total_count)  # pct

        t5 = perftime.perf_counter()
        non_pv_npsresponse_ids = list(NPSResponse.objects.filter(customer__border3__isnull=True).values_list('id', flat=True))
        non_pv_total_count = len(non_pv_npsresponse_ids)
        t6 = perftime.perf_counter()
        non_pv_histogram = [['Detractors (0-6)', 0, 0], ['Passives (7-8)', 0, 0], ['Promoters (9-10)', 0, 0]]
        with connection.cursor() as cursor:
            sql = f"select width_bucket(score, array[0,7,9]) as bucket, count(*) " \
                  f"from ishamba.customers_npsresponse " \
                  f"where customers_npsresponse.id IN ({','.join(map(str, non_pv_npsresponse_ids))}) " \
                  f"group by bucket order by bucket;"
            cursor.execute(sql, )
            data = cursor.fetchall()
            for row in data:
                non_pv_histogram[row[0] - 1][1] = row[1]  # count
                non_pv_histogram[row[0] - 1][2] = 100 * (row[1] / non_pv_total_count)  # pct
        t7 = perftime.perf_counter()
        logger.debug(
            f"NPSView.get_context: t2: {t2 - t1:0.1f}, t3: {t3 - t2:0.1f}, t4: {t4 - t3:0.1f}, t5: {t5 - t4:0.1f}, t6: {t6 - t5:0.1f}, t7: {t7 - t6:0.1f}"
        )
        context.update({
            'nps_score': nps_total_histogram[2][2] - nps_total_histogram[0][2],
            'nps_total_count': nps_total_count,
            'nps_total_response_rate': nps_total_response_rate,
            'nps_pv_score':  pv_histogram[2][2] - pv_histogram[0][2],
            'nps_non_pv_score':  non_pv_histogram[2][2] - non_pv_histogram[0][2],
            'nps_total_histogram': nps_total_histogram,
        })
        return context
