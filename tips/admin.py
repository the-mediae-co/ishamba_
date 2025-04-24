from datetime import datetime, timedelta
import humanize
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import FormActions
from crispy_forms.layout import Div, Layout, Row, Submit

from django import forms, template
from django.core.exceptions import ValidationError
from django.contrib import admin
from django.db.models import Count
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.urls import re_path
from django.utils.timezone import localtime, make_aware, now
from django.utils.translation import gettext_lazy as _

from import_export.admin import ImportExportMixin
from durationwidget.widgets import TimeDurationWidget

from core.admin import TimestampedBaseAdmin
from core.importer import resources
from core.utils.functional import is_jquery_ajax
from core.widgets import AuthModelSelect2Widget, AuthModelSelect2MultipleWidget, HTML5DateTimeInput
from customers.models import Customer, CustomerCategory
from world.models import Border
from .models import BulkTipSeriesSubscription, Tip, TipSeries, TipSeriesSubscription, TipTranslation

logger = logging.getLogger(__name__)
register = template.Library()


class TipBorder1Filter(admin.SimpleListFilter):
    title = _("border1")
    parameter_name = "border1"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [
            (b1[0], f"{b1[1]} ({b1[2]})")
            for b1 in Border.objects.filter(level=1)
            .order_by("country", "name")
            .values_list("pk", "name", "country")
        ]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if not self.value():
            return queryset
        return queryset.filter(border1_id=self.value())


class TipAdminForm(forms.ModelForm):
    delay = forms.DurationField(widget=TimeDurationWidget(show_days=True, show_hours=True,
                                                          show_minutes=False, show_seconds=False),
                                required=False)

    class Meta:
        fields = '__all__'
        model = Tip


class TipTranslationInlineForm(forms.BaseInlineFormSet):
    """
    Protect against multiple entries for the same language.
    Protect against zero translations.
    """
    def clean(self):
        super().clean()
        num_forms = self.data.get('translations-TOTAL_FORMS')
        if not num_forms or int(num_forms) < 1:
            raise ValidationError(f"At least one translation is required.")
        num_forms = int(num_forms)
        languages = {}
        for n in range(num_forms):
            lang = self.data.get(f'translations-{n}-language')
            delete = self.data.get(f'translations-{n}-DELETE')
            if delete and delete == 'on':
                num_forms -= 1
            else:
                if lang and lang in languages:
                    raise ValidationError(f"Only one translation for each language is allowed.")
            languages[lang] = True
        if num_forms < 1:
            raise ValidationError(f"At least one translation is required.")
        return self.data


class TipTranslationInline(admin.TabularInline):
    model = TipTranslation
    extra = 0
    can_delete = True
    formset = TipTranslationInlineForm
    exclude = ('creator_id', 'created', 'last_editor_id', 'last_updated')
    verbose_name = 'translation'
    verbose_name_plural = 'translations'


@admin.register(Tip)
class TipAdmin(TimestampedBaseAdmin):
    form = TipAdminForm
    fields = ('commodity', 'delay', 'border1', )
    list_display = ('commodity', 'sending_delay', 'border1', )
    list_filter = ('commodity', TipBorder1Filter, )
    ordering = ('commodity__name', 'delay', 'border1__name', )


    inlines = [
        TipTranslationInline,
    ]

    @admin.display(
        description='Sending delay',
        ordering='delay',
    )
    def sending_delay(self, obj):
        return f'{obj.delay}'


# class TipInlineForm(forms.BaseInlineFormSet):
#     """
#     Change the queryset for Tip choice menu to include only the
#     tips associated with this TipSeries, sorted by delay.
#     """
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         for form in self.forms:
#             instance = kwargs.get('instance')
#             # if instance:
#             #     form.fields['series'].queryset = Tip.objects.filter(series=instance).order_by('delay')


class TipInline(admin.TabularInline):
    model = Tip
    extra = 1
    can_delete = True
    # formset = TipInlineForm
    fields = ('delay', 'border1',)
    exclude = ('creator_id', 'created', 'last_editor_id', 'last_updated',)


@admin.register(TipSeries)
class TipSeriesAdmin(TimestampedBaseAdmin):
    list_display = ("name", "commodity", "subscriber_count", "start_event", "end_message")
    fields = ("name", "commodity", "subscriber_count", "start_event", "end_message")
    readonly_fields = ("subscriber_count",)
    search_fields = ('name', 'commodity__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(subscriber_count=Count("subscriptions"))

    @admin.display(
        description="# Subscribed",
        ordering="subscriber_count",
    )
    def subscriber_count(self, obj):
        return f"{humanize.intcomma(obj.subscriber_count)}"


class TipSeriesSubscriptionAdminForm(forms.ModelForm):
    start = forms.DateTimeField(
        required=True,
        widget=HTML5DateTimeInput(),
        initial=localtime(now()).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
    )

    class Meta:
        fields = '__all__'
        model = TipSeriesSubscription

    def clean_start(self):
        today = localtime(now())
        start = self.cleaned_data['start']
        if start.year != today.year and start.year != today.year + 1:
            raise ValidationError(f"Year is not correct.")
        delta = abs((start - today).days)  # days from today
        if delta > 30 and (start.day != 1 or start.month != 1):
            raise ValidationError(f"Start date must be the first day of a year or within 30 days of today.")
        return start

    def clean(self):
        # Restrict number of subscriptions
        customer = self.cleaned_data['customer']
        if customer is None:
            raise ValidationError("Customer is unknown")
        max_allowed = customer.subscriptions.get_usage_allowance('tips')
        usage = customer.tip_subscriptions.filter(ended=False).count()
        if usage > max_allowed:
            raise ValidationError("You can only set {} tip series subscriptions "
                                  "for this customer".format(max_allowed))


class TipSeriesSubscriptionActiveFilter(admin.SimpleListFilter):
    title = _("active")
    parameter_name = "ended"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ("active", _("Active")),
            ("ended", _("Ended")),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if self.value() == "active":
            return queryset.filter(ended=False)
        elif self.value() == "ended":
            return queryset.filter(ended=True)
        else:
            return queryset


class TipSeriesSubscriptionStartFilter(admin.SimpleListFilter):
    title = _("start")
    parameter_name = "start"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        years = range(now().year - 1, 2014, -1)
        choices = [
            ("today", _("today")),
            ("week", _("past week")),
            ("month", _("past 4 weeks")),
            ("year", _("this year")),
        ]
        choices.extend([(year, str(year)) for year in years])
        return choices

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if self.value() is None:
            return queryset

        today = localtime(now()).replace(hour=0, minute=0, second=0, microsecond=0)
        if self.value().isnumeric():
            start_date = make_aware(datetime(int(self.value()), 1, 1)).isoformat()
            end_date = make_aware(datetime(int(self.value()), 12, 31)).isoformat()
            return queryset.filter(start__gte=start_date, start__lte=end_date)
        else:  # Labeled string values override a year selection
            if self.value() == "today":
                filter_date = today
            elif self.value() == "week":
                filter_date = today - timedelta(days=7)
            elif self.value() == "month":
                filter_date = today - timedelta(weeks=4)
            elif self.value() == "year":
                filter_date = today.replace(day=1, month=1)
            else:
                return queryset

            return queryset.filter(
                start__gte=filter_date.isoformat(), start__lte=today.isoformat()
            )


@admin.register(TipSeriesSubscription)
class TipSeriesSubscriptionAdmin(ImportExportMixin, TimestampedBaseAdmin):
    form = TipSeriesSubscriptionAdminForm
    list_display = (
        "customer",
        "series",
        "start",
        "active",
    )
    # list_display = ('customer', 'series', 'start', 'expire', 'active', )
    readonly_fields = ("active",)
    # readonly_fields = ('expire', 'active', )
    raw_id_fields = ("customer",)
    resource_class = resources.TipSeriesSubscriptionResource
    list_filter = (
        TipSeriesSubscriptionActiveFilter,
        TipSeriesSubscriptionStartFilter,
        "series",
    )
    ordering = (
        "-start",
        "series",
    )

    def get_changeform_initial_data(self, request):
        return {'start': localtime(now()).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)}

    @admin.display(
        description="Active",
        # ordering='-expire',
    )
    def active(self, obj):
        return not obj.ended

    active.boolean = True

    @admin.display(
        description="Starts",
        ordering="start",
    )
    def start(self, obj):
        return f"{humanize.naturaldate(obj.start)}"

    def save_model(self, request, tip_subscription, form, change):
        customer = tip_subscription.customer
        commodity = tip_subscription.series.commodity

        # Add the commodity for this subscription to the customer's set
        if commodity is not None and customer is not None:
            customer.commodities.add(commodity)

        super().save_model(request, tip_subscription, form, change)


class BulkTipSeriesSubscriptionForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        required=True,
        queryset=CustomerCategory.objects.none(),  # Set in __init__
        label=_("Categories of customers to subscribe"),
        widget=AuthModelSelect2MultipleWidget(
            model=CustomerCategory,
            queryset=CustomerCategory.objects.none(),  # Set in __init__
            search_fields=['name__icontains'],
            max_results=300,
            attrs={'data-minimum-input-length': 0},
        ),
    )
    tip_series = forms.ModelChoiceField(
        required=True,
        queryset=TipSeries.objects.none(),  # Set in __init__
        label=_("Tip Series to subscribe customers to"),
        widget=AuthModelSelect2Widget(
            model=TipSeries,
            queryset=TipSeries.objects.none(),  # Set in __init__
            search_fields=['name__icontains'],
            max_results=100,
            attrs={'data-minimum-input-length': 0},
        ),
    )
    start = forms.DateTimeField(
        required=True,
        widget=HTML5DateTimeInput(),
        # initial=date.today().replace(month=1, day=1),
        initial=localtime(now()).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
    )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Div(
                Row('category', ),
                Row('customer_count', ),
                Row('tip_series', ),
                Row('start', ),
            ),
            FormActions(
                Submit('submit', 'Subscribe', css_class='btn btn-primary')
                # Unfortunately, crispyforms doesn't handle a form submit element without class = btn-primary
                # so we can't style the export button as secondary. The work-around is to insert raw HTML.
                # HTML("""
                # <input type="submit" name="export" value="Export CSV" class="btn btn-secondary" id="button-id-export">
                # """),
                # Button('export', 'Export CSV', css_class='btn btn-secondary'),
            ),
        )
        super().__init__(*args, **kwargs)
        self.fields['categories'].queryset = CustomerCategory.objects.order_by(Lower('name'))
        self.fields['categories'].widget.queryset = CustomerCategory.objects.order_by(Lower('name'))
        self.fields['tip_series'].queryset = TipSeries.objects.order_by(Lower('name'))
        self.fields['tip_series'].widget.queryset = TipSeries.objects.order_by(Lower('name'))

    def get_context(self):
        return super().get_context()
        pass

    def clean_start(self):
        today = localtime(now())
        start = self.cleaned_data['start']
        if start.year != today.year and start.year != today.year + 1:
            raise ValidationError(f"Year is not correct.")
        delta = abs((start - today).days)  # days from today
        if delta > 30 and (start.day != 1 or start.month != 1):
            raise ValidationError(f"Start date must be the first day of a year or within 30 days of today.")
        return start

    def clean(self):
        categories = self.cleaned_data["categories"]
        # Get all customers in the specified categories
        category_pks = categories.values_list("pk", flat=True)
        customer_count = Customer.objects.filter(categories__pk__in=category_pks).count()
        if customer_count == 0:
            raise ValidationError(
                f"The selected {'category contains' if customer_count == 1 else 'categories contain'} no customers."
            )
        return super().clean()


@admin.register(BulkTipSeriesSubscription)
class BulkTipSeriesSubscriptionAdmin(TimestampedBaseAdmin):
    form = BulkTipSeriesSubscriptionForm

    class Media:
        js = ('js/bulk-tip-series-subscription.js', )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            re_path(r'^count_customers/$', self.admin_site.admin_view(self.count_customers),
                    name='bulk_tipseries_category_count'),
        ]
        return my_urls + urls

    def count_customers(self, request):
        if is_jquery_ajax(request):
            keys = request.POST.getlist('selections[]')
            customers = Customer.objects.filter(categories__pk__in=keys)
            return JsonResponse({'count': customers.count()})

    def save_model(self, request, bulk_subscription, form, change):
        bulk_subscription.creator_id = request.user.id
        categories = form.cleaned_data['categories']
        series = form.cleaned_data['tip_series']
        start = form.cleaned_data['start']

        # Get all customers in the specified categories
        category_ids = categories.values_list('pk', flat=True)
        customer_ids = Customer.objects.filter(categories__pk__in=category_ids).values_list('pk', flat=True)

        # Remove any who are already subscribed to this tip_series
        existing_pks = TipSeriesSubscription.objects.filter(
            customer_id__in=customer_ids, series=series
        ).values_list("customer_id", flat=True)

        new_pks = customer_ids.difference(existing_pks)

        # Create new subscriptions for those who are not already subscribed
        new_subscriptions = []
        counter = 0
        for customer_id in new_pks:
            tss = TipSeriesSubscription(
                customer_id=customer_id,
                series=series,
                start=start,
                ended=False,
            )
            new_subscriptions.append(tss)
            counter += 1
            if counter % 1000 == 0:
                TipSeriesSubscription.objects.bulk_create(new_subscriptions)
                new_subscriptions = []

        if new_subscriptions:
            TipSeriesSubscription.objects.bulk_create(new_subscriptions)

        super().save_model(request, bulk_subscription, form, change)
