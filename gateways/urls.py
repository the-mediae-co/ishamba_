from django.conf.urls import include
from django.urls import re_path

app_name = 'gateways'

urlpatterns = [
    re_path(
        r'^africastalking/',
        include(
            'gateways.africastalking.urls',
            namespace='africastalking'
        )
    )
]
