from django.urls import re_path
from django.contrib.auth.decorators import login_required

from .. import views

urlpatterns = [
    re_path(
        r'^$',
        login_required(views.OfferListView.as_view()),
        name='offer_list'),
    re_path(
        r'^new_verify_in_store/$',
        login_required(views.VerifyInStoreOfferCreateView.as_view()),
        name='verify_in_store_offer_create'),
    re_path(
        r'^new_free_subscription/$',
        login_required(views.FreeSubscriptionOfferCreateView.as_view()),
        name='free_subscription_offer_create'),
    re_path(
        r'^(?P<pk>\d+)/$',
        login_required(views.OfferDetailView.as_view()),
        name='offer_detail'),
    re_path(
        r'^(?P<pk>\d+)/edit/$',
        login_required(views.OfferUpdateView.as_view()),
        name='offer_update'),
    re_path(
        r'^(?P<pk>\d+)/filter/$',
        login_required(views.OfferFilterCustomersView.as_view()),
        name='offer_filter_customers'),
    re_path(
        r'^verify/$',
        login_required(views.OfferVerifyView.as_view()),
        name='offer_verify'),
]
