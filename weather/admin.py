from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

# from leaflet.admin import LeafletGeoAdmin

from core.admin import TimestampedBaseAdmin, TimestampedBaseAdminMixin
from weather.models import CountyForecast, ForecastDay, WeatherArea
from world.models import Border


class ForecastCountyFilter(admin.SimpleListFilter):
    title = _("county")
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
            .values_list("id", "name", "country")
        ]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if not self.value():
            return queryset
        return queryset.filter(county_id=self.value())


class CountyForecastAdminForm(forms.ModelForm):
    class Meta:
        fields = ['dates', 'county', 'category', 'text', 'premium_only']
        model = CountyForecast
        widgets = {
            'text': forms.Textarea(attrs={'rows': 10, 'cols': 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county'].queryset = Border.objects.filter(country='Kenya', level=1)


class CountyForecastAdmin(TimestampedBaseAdmin):
    form = CountyForecastAdminForm
    fields = ('dates', 'county', 'category', 'text', 'premium_only')
    list_display = ('county', 'dates', 'category', 'premium_only', )
    list_filter = ('premium_only', ForecastCountyFilter, 'category', )


# class ForecastDayAdmin(TimestampedBaseAdmin):
#     pass


# class WeatherAreaAdmin(TimestampedBaseAdminMixin, LeafletGeoAdmin):
#
#     modifiable = False  # applies to the geo fields
#     list_display = ('id', 'count_customers', )
#
#     def count_customers(self, obj):
#         return obj.customer_set.count()
#     count_customers.short_description = 'Customer count'


admin.site.register(CountyForecast, CountyForecastAdmin)
# admin.site.register(ForecastDay, ForecastDayAdmin)
# admin.site.register(WeatherArea, WeatherAreaAdmin)
