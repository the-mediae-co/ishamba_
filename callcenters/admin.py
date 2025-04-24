from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from callcenters.models import CallCenter, CallCenterOperator, CallCenterSender


class CallCenterAnalystInline(admin.TabularInline):
    model = CallCenterOperator


@admin.register(CallCenter)
class CallCenterAdmin(admin.ModelAdmin):
    autocomplete_fields = ['border']
    inlines = [CallCenterAnalystInline]


class OperatorAdmin(UserAdmin):
    inlines = [CallCenterAnalystInline]

admin.site.unregister(User)
admin.site.register(User, OperatorAdmin)
admin.site.register(CallCenterSender)
