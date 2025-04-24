from django.contrib import admin

from core.admin import TimestampedBaseAdmin, TimestampedBaseAdminMixin
from subscriptions.models import SubscriptionType, Subscription, SubscriptionAllowance


@admin.register(Subscription)
class SubscriptionAdmin(TimestampedBaseAdmin):
    list_display = ('customer', 'start_date', 'end_date')
    search_fields = ('customer__name', 'customer__phones__number')
    list_filter = ('start_date', 'end_date')
    raw_id_fields = ('customer',)


class SubscriptionAllowanceInline(TimestampedBaseAdminMixin, admin.TabularInline):
    model = SubscriptionAllowance
    extra = 1



@admin.register(SubscriptionType)
class SubscriptionTypeAdmin(TimestampedBaseAdmin):
    fields = ('name', 'end_message', 'is_permanent',)
    inlines = [SubscriptionAllowanceInline]
