from django.contrib import admin
from django.forms import ModelForm

from import_export.admin import ImportExportMixin

from core.admin import TimestampedBaseAdmin
from core.importer.resources import MarketPriceResource, MarketSubscriptionResource
from markets.models import Market, MarketPrice, MarketSubscription
from world.admin import iShambaMapWidget


class MarketAdminForm(ModelForm):
    class Meta:
        model = Market
        fields = '__all__'
        widgets = {'location': iShambaMapWidget()}


@admin.register(Market)
class MarketAdmin(TimestampedBaseAdmin):
    form = MarketAdminForm



@admin.register(MarketPrice)
class MarketPriceAdmin(ImportExportMixin, TimestampedBaseAdmin):
    resource_class = MarketPriceResource
    list_display = ('market', 'commodity', 'date', 'display_amount', 'price')
    search_fields = ('market__name', 'commodity__name')
    list_filter = ('market', 'commodity', 'date')
    fields = ('market', 'commodity', 'date', 'source', 'amount', 'price', 'unit')


@admin.register(MarketSubscription)
class MarketSubscriptionAdmin(ImportExportMixin, TimestampedBaseAdmin):
    resource_class = MarketSubscriptionResource

    list_display = ('customer', 'market', 'backup')
    search_fields = ('customer__name', 'customer__phones__number')
    list_filter = ('market', 'backup')
    raw_id_fields = ('customer',)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'model_name': 'MarketSubscription'})
        return context
