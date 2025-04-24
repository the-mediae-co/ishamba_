from django.contrib import admin
from djangoql.admin import DjangoQLSearchMixin

from calls.models import Call, CallCenterPhone, PusherSession


class CallAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ('created_on', 'caller_number', 'destination_number',
                    'customer', 'duration', 'cost',
                    'cco', 'is_active', 'connected', )
    list_filter = ('is_active', 'connected', 'cco', )
    readonly_fields = ('caller_number', 'customer', 'provided_id', 'cco', 'direction', )


class CallCenterPhoneAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'is_active', )


class PusherSessionAdmin(admin.ModelAdmin):
    list_display = ('call_center_phone', 'operator', 'pusher_session_key',
                    'created_on', 'finished_on', )


admin.site.register(Call, CallAdmin)
admin.site.register(CallCenterPhone, CallCenterPhoneAdmin)
admin.site.register(PusherSession, PusherSessionAdmin)
