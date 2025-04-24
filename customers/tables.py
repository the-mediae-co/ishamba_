from datetime import timedelta

from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import formats
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

import django_tables2 as tables
from django_tables2.utils import A

from agri.models import Commodity
from calls.models import Call
from customers.models import Customer, CropHistory, CustomerCommodity
from markets.models import MarketSubscription
from sms.constants import OUTGOING_SMS_TYPE
from sms.models import OutgoingSMS, IncomingSMS
from tasks.models import Task
from tips.models import TipSent
from subscriptions.models import Subscription


class CustomerTable(tables.Table):
    bulk = tables.TemplateColumn(template_name='customers/partials/bulk_column.html',
                                 verbose_name='',
                                 orderable=False)
    name = tables.LinkColumn(
        'customers:customer_detail',
        args=[A('pk')],
        empty_values=(),
        text=lambda r: r.name if r.name else mark_safe('&mdash;')
    )
    dob = tables.Column(accessor="dob", verbose_name=_("DOB"), visible=False)
    location = tables.BooleanColumn()
    border0 = tables.Column(accessor="border0", verbose_name=_("Country"))
    border1 = tables.Column(accessor="border1", verbose_name=_("County/Region"))
    border2 = tables.Column(accessor="border2", verbose_name=_("Sub County/Sub Region"), visible=False)
    border3 = tables.Column(accessor="border3", verbose_name=_("Ward/District"), visible=False)
    formatted_phone = tables.Column(accessor="formatted_phone", verbose_name=_("Phone Number"), visible=False)
    gps_coordinates = tables.Column(accessor="gps_coordinates", verbose_name=_("Long, Lat"), visible=False)
    subs_count = tables.Column(accessor="subs_count", verbose_name=_("Subscriptions"), visible=False)
    calls_count = tables.Column(accessor="calls_count", verbose_name=_("Calls"), visible=False)
    sms_count = tables.Column(accessor="sms_count", verbose_name=_("SMS"), visible=False)
    commodity_names = tables.Column(accessor="commodity_names", verbose_name=_("Commodities"), visible=False)
    crop_histories_count = tables.Column(accessor="crop_histories_count", verbose_name=_("Crop Histories"), visible=False)

    class Meta:
        model = Customer
        fields = (
            'bulk', 'id', 'name', 'sex', 'dob', 'phone_type', 'formatted_phone',
            'location', 'border0', 'border1', 'border2', 'border3',
            'agricultural_region', 'categories', 'gps_coordinates',
            'subs_count', 'calls_count', 'sms_count', 'commodity_names', 'crop_histories_count',
        )
        order_by = ('-id', )
        attrs = {"class": "table-bordered"}
        empty_text = "No customers"
        template_name = 'tables/tables.html'

    def value_name(self, record, value):
        """Don't return an html emdash if there is no name"""
        return value

    def render_border0(self, value, record, bound_column):
        ctx = {'country': value.name}
        return render_to_string('customers/partials/country.html', ctx)


class CallHistoryTable(tables.Table):

    class Meta:
        model = Call
        fields = ('created_on', 'duration', 'duration_in_queue', 'cco',
                  'notes', 'issue_resolved')
        order_by = ('-created_on', )
        attrs = {"class": "table-bordered"}
        empty_text = "No previous calls"


class SubscriptionHistoryTable(tables.Table):
    creator = tables.Column(orderable=False)

    class Meta:
        model = Subscription
        fields = ('start_date', 'end_date')
        # order_by = ('-end_date', )
        attrs = {"class": "table-bordered"}
        empty_text = "No subscriptions"


class CropHistoryTable(tables.Table):
    estimated_season_end_date = tables.DateColumn()
    edit = tables.TemplateColumn(
        orderable=False,
        template_code="""
        <a href="{% url 'customers:customer_crop_history_update' record.pk %}" class="btn btn-primary">Edit</a>
        """
    )
    delete = tables.TemplateColumn(
        orderable=False,
        template_code="""
        <a href="{% url 'customers:customer_crop_history_delete' record.pk %}" class="btn btn-primary">Delete</a>
        """
    )

    class Meta:
        model = CropHistory
        fields = ('commodity', 'date_planted', 'estimated_season_end_date', 'used_certified_seed', 'acres_planted',
                  'cost_of_seeds', 'cost_of_fertilizer', 'cost_currency', 'harvest_amount', 'harvest_units',
                  'edit', 'delete')
        order_by = ('-date_planted', )
        attrs = {"class": "table-bordered"}
        empty_text = "No crop history for this customer"

    def render_date_planted(self, record):
        date_planted = formats.date_format(record.date_planted, use_l10n=True)
        return date_planted

    def render_estimated_season_end_date(self, record):
        season_end = "—"
        commodity = record.commodity
        if commodity.is_crop and commodity.season_length_days:
            season_end_date = record.date_planted + timedelta(days=commodity.season_length_days)
            season_end = formats.date_format(season_end_date, use_l10n=True)
        return season_end


class CommodityTable(tables.Table):
    delete = tables.Column(
        orderable=False,
        linkify=False,
        empty_values=(),
    )
    market_subscription = tables.Column(
        orderable=True,
        linkify=False,
        empty_values=(),
    )
    tip_subscription = tables.Column(
        orderable=True,
        linkify=False,
        empty_values=(),
        verbose_name=_('Active tip series subscription')
    )

    class Meta:
        model = Commodity
        fields = ('name', 'variant_of', 'commodity_type', 'tip_subscription', 'market_subscription', 'delete')
        attrs = {"class": "table-bordered"}
        empty_text = "No commodities"

    def __init__(self, customer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.customer = customer

    def render_delete(self, record):
        tip_subscribed = self.customer.tip_subscriptions.filter(ended=False, series__commodity=record).exists()
        market_subscribed = self.customer.market_subscriptions.filter(commodity=record).exists()
        if tip_subscribed or market_subscribed:
            form_action = None
            form_method = None
        else:
            form_method = "post"
            form_action = reverse(
                "customers:customer_commodity_remove",
                kwargs={
                    "pk": record.pk,
                    'c_pk': self.customer.pk,
                },
            )
        context = {
            'form_action': form_action,
            'button_title': _('Remove'),
            'form_method': form_method,
            'disable': tip_subscribed or market_subscribed,
        }
        return render_to_string('customers/partials/form_button.html', context, request=self.context.request)

    def render_tip_subscription(self, record):
        subscribed = record.id in self.customer.tips_commodities
        customer_commodity = self.customer.customer_commodities.filter(commodity=record).first()
        subscription_flag = f"{customer_commodity.get_subscription_flag_display()} " if customer_commodity else ""
        if subscribed:
            return f"{subscription_flag}Enabled: ✅"
        else:
            return f"{subscription_flag}Disabled: ✘"

    def render_market_subscription(self, record):
        subscribed = self.customer.market_subscriptions.filter(commodity=record).exists()
        if subscribed:
            return "✅"
        else:
            return "—"


class MarketSubscriptionTable(tables.Table):
    edit = tables.Column(
        orderable=False,
        linkify=False,
        empty_values=(),
    )
    delete = tables.Column(
        orderable=False,
        linkify=False,
        empty_values=(),
    )

    class Meta:
        model = MarketSubscription
        fields = ('market', 'backup', 'commodity', 'edit', 'delete')
        attrs = {"class": "table-bordered"}
        empty_text = "No market price subscriptions"

    def render_edit(self, record):
        form_action = reverse('customers:customer_market_subscription_update',
                              kwargs={
                                  'c_pk': record.customer.pk,
                                  'pk': record.pk,
                              })
        context = {
            'form_action': form_action,
            'button_title': _('Edit'),
            'form_method': 'get',
            'disable': False,
        }
        return render_to_string('customers/partials/form_button.html', context, request=self.context.request)

    def render_delete(self, record):
        form_action = reverse('customers:customer_market_subscription_delete',
                              kwargs={
                                  'c_pk': record.customer.pk,
                                  'pk': record.pk,
                              })
        context = {
            'form_action': form_action,
            'button_title': _('Delete'),
            'form_method': 'post',
            'disable': False,
        }
        return render_to_string('customers/partials/form_button.html', context, request=self.context.request)


class TipSeriesSubscriptionTable(tables.Table):
    commodity = tables.LinkColumn('customers:customer_tip_subscription_update',
                               args=[A('pk')])
    created = tables.DateColumn(verbose_name="Created")
    delete = tables.Column(
        orderable=False,
        linkify=False,
        empty_values=(),
    )

    class Meta:
        model = CustomerCommodity
        fields = ('commodity', 'primary', 'subscription_flag', 'created', 'delete')
        attrs = {"class": "table-bordered"}
        empty_text = "No tip series subscriptions"

    def render_delete(self, record):
        form_action = reverse('customers:customer_tip_subscription_delete',
                              kwargs={'pk': record.pk})
        context = {
            'form_action': form_action,
            'button_title': _('Delete'),
            'form_method': 'post',
            'disable': False,
        }
        return render_to_string('customers/partials/form_button.html', context, request=self.context.request)

    def render_ended(self, value):
        if value:
            return "\u274C " + _("Ended")
        else:
            return "✅ " + _("Running")

# The following should strictly be in their respective app folders, but they're
# all very similar and fairly trivial.


class IncomingSMSTable(tables.Table):

    tasks = tables.Column(empty_values=(), orderable=False)
    response = tables.Column(empty_values=(), orderable=False)

    class Meta:
        model = IncomingSMS
        fields = ('at', 'text')
        sequence = ('at', 'text', 'response', 'tasks')
        attrs = {"class": "table-bordered"}
        empty_text = "No SMS messages received from this customer."
        template_name = "tables/tables.html"

    def render_tasks(self, value, record, bound_column):
        tasks = Task.objects.filter(incoming_messages__pk=record.pk)
        ctx = {'tasks': tasks}
        return render_to_string('customers/partials/tasks_column.html', ctx)

    def render_response(self, value, record, bound_column):
        # Most incoming messages turn into tasks, so check those first
        task = Task.objects.filter(incoming_messages__pk=record.pk).first()
        if task:
            outgoing_messages = [out.text for out in task.outgoing_messages.all()]
            # outgoing_messages = OutgoingSMS.objects.filter(message_type='task', pk__in=task_ids)
        else:
            # If the incoming message didn't create a task, check if it generated a template response
            outgoing_messages = OutgoingSMS.objects.filter(message_type=OUTGOING_SMS_TYPE.TEMPLATE_RESPONSE,
                                                           incoming_sms__pk=record.pk).values_list('text', flat=True)

        return ','.join(outgoing_messages)


class OutgoingSMSTable(tables.Table):

    class Meta:
        model = OutgoingSMS
        fields = ('message_type', 'sent_by', 'sent_at', 'text')
        attrs = {"class": "table-bordered"}
        empty_text = "No SMS messages of this type sent to this customer."
        template_name = "tables/tables.html"


class TipSentTable(tables.Table):
    created = tables.DateTimeColumn(verbose_name='Created')
    tip = tables.Column(accessor='tip__text', verbose_name='Text')
    series = tables.Column(accessor='tip__series', verbose_name='Series')

    class Meta:
        models = TipSent
        fields = ('created', 'tip',)
        attrs = {"class": "table-bordered"}
        empty_text = "No tips have been sent to this customer."
        template_name = "tables/tables.html"
