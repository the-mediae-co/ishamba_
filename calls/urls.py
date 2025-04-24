from django.conf.urls import include
from django.urls import re_path
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

import calls.api
import calls.views
from django.conf import settings
from core.decorators import ip_authorisation

calls_urls = [
    re_path(r'^$',
            login_required(calls.views.CallsIndexFormView.as_view()),
            name='calls_index'),
    re_path(r'^call_queue/$',
            login_required(calls.views.CallQueueView.as_view()),
            name='call_queue'),
    re_path(r'^connected_calls/$',
            login_required(calls.views.ConnectedCallsView.as_view()),
            name='connected_calls'),
    re_path(r'^voice_api_callback/$',
            csrf_exempt(ip_authorisation(settings.AUTHORIZED_IPS)(calls.views.VoiceApiCallbackView.as_view())),
            name='voice_api_callback'),
    re_path(r'^pusher_api_callback/$',
            csrf_exempt(calls.views.PusherApiCallbackView.as_view()),
            name='pusher_api_callback'),
    re_path(r'^pusher_auth/$',
            calls.views.PusherAuthView.as_view(),
            name='pusher_auth'),
]

api_urls = [
    re_path(r'^call/(?P<pk>\d+)/$',
            login_required(calls.api.CallDetailView.as_view()),
            name='api_call_detail_view'),
    re_path(r'^cco/(?P<username>\w+)/$',
            login_required(calls.api.CCOView.as_view()),
            name='api_cco_view'),
    re_path(r'^weather_area/(?P<pk>\w+)/forecast_days/$',
            login_required(calls.api.ForecastDayListView.as_view()),
            name='api_forecast_day_list_view'),
    re_path(r'^commodity/(?P<pk>\w+)/latest_prices/$',
            login_required(calls.api.MarketPriceListView.as_view()),
            name='api_market_price_list_view'),
    re_path(r'^customer/(?P<pk>\w+)/outgoing_sms/$',
            login_required(calls.api.OutgoingSMSListView.as_view()),
            name='api_outgoing_sms_list_view'),
    re_path(r'^customer/(?P<pk>\w+)/incoming_sms/$',
            login_required(calls.api.IncomingSMSListView.as_view()),
            name='api_incoming_sms_list_view'),
]

urlpatterns = [
    re_path(r'^api/', include(api_urls)),
    re_path(r'^', include(calls_urls)),
]
