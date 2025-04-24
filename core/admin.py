from typing import List, Optional, Tuple, Union
from django.contrib import admin
from django.contrib.sites.models import Site
from django.db.models.base import Model
from django.http.request import HttpRequest
from django_tenants.admin import TenantAdminMixin

from core.models import Client

from django_tenants.admin import TenantAdminMixin

from core.models import Client


admin.site.unregister(Site)  # Don't let users change the Site


class TimestampedBaseAdminMixin(object):
    our_exclude_fields = ('creator_id', 'created', 'last_editor_id', 'last_updated')
    our_ro_fields = ()

    def get_readonly_fields(self, request: HttpRequest, obj: Optional[Model] = None) -> Union[List[str], Tuple]:
        if issubclass(self.__class__, admin.ModelAdmin):
            try:
                ro_fields = super(admin.ModelAdmin, self).get_readonly_fields(request, obj) or ()
            except AttributeError:
                ro_fields = ()
            return ro_fields + self.our_ro_fields
        else:
            return ()

    def get_exclude(self, request: HttpRequest, obj: Optional[Model] = None) -> Union[List[str], Tuple]:
        if issubclass(self.__class__, admin.ModelAdmin):
            try:
                exclude_fields = super(admin.ModelAdmin, self).get_exclude(request, obj) or ()
            except AttributeError:
                exclude_fields = ()
            return exclude_fields + self.our_exclude_fields
        else:
            return ()

    def save_model(self, request, obj, form, change):
        obj.save(user=request.user)


class TimestampedBaseAdmin(TimestampedBaseAdminMixin, admin.ModelAdmin):
    pass


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    pass
