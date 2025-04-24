from django.contrib import admin

from agri.models.base import Commodity, Region
# from agri.models.messaging import AgriTipSMS
from core.admin import TimestampedBaseAdmin


@admin.register(Region)
class RegionAdmin(TimestampedBaseAdmin):
    pass


@admin.register(Commodity)
class CommodityAdmin(TimestampedBaseAdmin):
    list_display = ('name', 'short_name', 'variant_of', 'gets_market_prices', )
    list_filter = ('gets_market_prices', )


# @admin.register(AgriTipSMS)
# class AgriTipSMS(TimestampedBaseAdmin):
#     list_display = ('commodity', 'region', 'number', 'text', )
#     readonly_fields = ('number', )
#     list_filter = ('region', 'commodity', )
#     ordering = ('commodity', 'region', 'number', )
