from django.contrib import admin

from core.admin import TimestampedBaseAdmin
from . import models


class TaskAdmin(TimestampedBaseAdmin):
    raw_id_fields = ('customer', 'outgoing_messages', 'incoming_messages',)


class TaskUpdateAdmin(TimestampedBaseAdmin):
    list_display = ('id', 'task', 'message', 'status')
    search_fields = ('message', )
    list_filter = ('status', )


admin.site.register(models.Task, TaskAdmin)
admin.site.register(models.TaskUpdate, TaskUpdateAdmin)
