from django.contrib.admin import ModelAdmin
from django.contrib.gis import admin as gis_admin
from django.contrib.gis.forms.widgets import BaseGeometryWidget
from django.forms import ModelForm

from .models import Border


class iShambaMapWidget(BaseGeometryWidget):
    template_name = 'admin/ishamba_map_widget.html'
    map_srid = 4326
    map_height = 360

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if value:
            context.update({'search_geom': value.json})
        return context


class BorderAdminForm(ModelForm):
    class Meta:
        model = Border
        fields = '__all__'
        widgets = {'border': iShambaMapWidget()}


@gis_admin.register(Border)
class BorderAdmin(ModelAdmin):
    # Disable the map editing controls in the LeafletWidget
    # https://docs.djangoproject.com/en/4.0/ref/contrib/gis/admin/#django.contrib.gis.admin.GeoModelAdmin.modifiable
    modifiable = False
    form = BorderAdminForm
    search_fields = ['country', 'name']
    list_filter = ['country', 'level']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Modify default behavior to disable the save buttons. Unfortunately making
        # this admin class non-changeable changes the behavior of the LeafletWidget
        # to display the raw GPS coordinates instead of the map. We want the map
        # to be visible, but not allow users to change any of the Border data.
        # See the note below this field: https://docs.djangoproject.com/en/4.0/ref/contrib/gis/admin/#django.contrib.gis.admin.GeoModelAdmin.modifiable
        extra_context = extra_context or {}
        extra_context['show_save_and_continue'] = False
        extra_context['show_save'] = False
        return super(BorderAdmin, self).change_view(request, object_id, form_url, extra_context=extra_context)
