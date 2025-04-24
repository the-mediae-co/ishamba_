from django.urls import re_path
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

import customers.views.customer as customer_views

app_name = 'customers'

urlpatterns = [
    # Customer CRUD
    re_path(
        r'^$',
        login_required(customer_views.CustomerListView.as_view()),
        name='customer_list'),
    re_path(
        r'^customer/new/$',
        login_required(customer_views.CustomerCreateView.as_view()),
        name='customer_create'),
    re_path(
        r'^customer/(?P<pk>\d+)/$',
        login_required(customer_views.CustomerDetailView.as_view()),
        name='customer_detail'),
    re_path(
        r'^customer/(?P<pk>\d+)/edit/$',
        login_required(customer_views.CustomerUpdateView.as_view()),
        name='customer_update'),

    # Market subscription CRUD
    re_path(
        r'^customer/(?P<pk>\d+)/markets/$',
        login_required(customer_views.MarketSubscriptionListView.as_view()),
        name='customer_market_subscription_list'),
    re_path(
        r'^customer/(?P<c_pk>\d+)/markets/(?P<pk>\d+)/$',
        login_required(customer_views.MarketSubscriptionUpdateView.as_view()),
        name='customer_market_subscription_update'),
    re_path(
        r'^customer/(?P<c_pk>\d+)/markets/(?P<pk>\d+)/delete/$',
        csrf_exempt(login_required(customer_views.MarketSubscriptionDeleteView.as_view())),
        name='customer_market_subscription_delete'),
    re_path(
        r'^customer/(?P<pk>\d+)/markets/new/$',
        login_required(customer_views.MarketSubscriptionCreateView.as_view()),
        name='customer_market_subscription_create'),

    # Tip subscription CRUD
    re_path(
        r'^customer/(?P<pk>\d+)/tips/$',
        login_required(customer_views.CustomerTipSubscriptionListView.as_view()),
        name='customer_tip_subscription_list'),
    re_path(
        r'^customer/tips/(?P<pk>\d+)/$',
        login_required(customer_views.CustomerTipSubscriptionUpdateView.as_view()),
        name='customer_tip_subscription_update'),
    re_path(
        r'^customer/tips/(?P<pk>\d+)/delete/$',
        csrf_exempt(login_required(customer_views.CustomerTipSubscriptionDeleteView.as_view())),
        name='customer_tip_subscription_delete'),
    re_path(
        r'^customer/(?P<pk>\d+)/tips/new/$',
        login_required(customer_views.CustomerTipSubscriptionCreateView.as_view()),
        name='customer_tip_subscription_create'),
    re_path(
        r'^customer/(?P<pk>\d+)/tips/history/$',
        login_required(customer_views.CustomerTipSentListView.as_view()),
        name='customer_tip_history'),

    # Commodity CRUD
    re_path(
        r'^customer/(?P<pk>\d+)/commodities/$',
        login_required(customer_views.CustomerCommodityListView.as_view()),
        name='customer_commodity_list'),
    re_path(
        r'^customer/(?P<c_pk>\d+)/commodities/(?P<pk>\d+)/remove/$',
        csrf_exempt(login_required(customer_views.CustomerCommodityRemoveView.as_view())),
        name='customer_commodity_remove'),
    re_path(
        r'^customer/(?P<pk>\d+)/commodities/add/$',
        login_required(customer_views.CustomerCommodityAddView.as_view()),
        name='customer_commodity_add'),

    # Calls
    re_path(
        r'^customer/(?P<pk>\d+)/call_history/$',
        login_required(customer_views.CustomerCallHistoryView.as_view()),
        name='customer_call_history'),

    # SMS
    re_path(
        r'^customer/(?P<pk>\d+)/sms/incoming/$',
        login_required(customer_views.IncomingSMSListView.as_view()),
        name='customer_incoming_sms_history'),
    re_path(
        r'^customer/(?P<pk>\d+)/sms/outgoing/$',
        login_required(customer_views.OutgoingSMSListView.as_view()),
        name='customer_outgoing_sms_history'),
    re_path(
        r'^customer/(?P<pk>\d+)/sms/outgoing/send/$',
        login_required(customer_views.SingleOutgoingSMSCreateView.as_view()),
        name='customer_send_outgoing_sms'),

    # Subscriptions
    re_path(
        r'^customer/(?P<pk>\d+)/subscriptions/$',
        login_required(customer_views.CustomerSubscriptionHistoryView.as_view()),
        name='customer_subscription_list'),

    # Activities
    re_path(
        r'^customer/(?P<pk>\d+)/activities/$',
        login_required(customer_views.CustomerActivityStreamView.as_view()),
        name='customer_activity_stream'),

    # Crop History
    re_path(
        r'^customer/(?P<pk>\d+)/crop_history/$',
        login_required(customer_views.CustomerCropHistoryListView.as_view()),
        name='customer_crop_history_list'),
    re_path(
        r'^customer/(?P<pk>\d+)/crop_history/new/$',
        login_required(customer_views.CustomerCropHistoryCreateView.as_view()),
        name='customer_crop_history_create'),
    re_path(
        r'^customer/crop_history/(?P<pk>\d+)/update/$',
        login_required(customer_views.CustomerCropHistoryUpdateView.as_view()),
        name='customer_crop_history_update'),
    re_path(
        r'^customer/crop_history/(?P<pk>\d+)/delete/$',
        login_required(customer_views.CustomerCropHistoryDeleteView.as_view()),
        name='customer_crop_history_delete'),
]
