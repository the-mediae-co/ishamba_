from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt

from . import views

app_name = 'africastalking'

urlpatterns = [
    # AfricasTalking incoming sms callback view
    re_path(
        r'^incoming-sms/$',
        csrf_exempt(views.ATIncomingSMSView.as_view()),
        name='incoming_sms'),

    # AfricasTalking delivery report callback view
    re_path(
        r'^delivery-report/$',
        csrf_exempt(views.ATDeliveryReportView.as_view()),
        name='delivery_report'),
]
