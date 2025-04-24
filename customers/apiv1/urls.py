from django.urls import re_path

from . import views

app_name = 'customers'

urlpatterns = [
    re_path(
        r'^customers/join/$',
        views.CustomerJoinView.as_view(),
        name='join'
    ),
    re_path(
        r'^customers/$',
        views.CustomerCreateView.as_view(),
        name='api-customer-create',
    ),
    # re_path(
    #     r'^customers/(?P<phone>\+[0-9]+)/$',
    #     views.CustomerDetailView.as_view(),
    #     name='api-customer-detail'
    # ),
    re_path(
        r'^subscriptions/$',
        views.SubscriptionCreateView.as_view(),
        name='api-subscription-create',
    ),
    re_path(
        r'^customers/chatbot/$',
        views.ChatbotTestingView.as_view(),
        name='chatbot'
    ),
]
