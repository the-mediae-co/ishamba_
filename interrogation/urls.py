from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt

from interrogation import views

app_name = 'interrogation'

urlpatterns = [
    re_path(r'^$', csrf_exempt(views.ussd_handler), name='interrogation'),
    re_path(r'^survey/(?P<survey_title>.+)/$', csrf_exempt(views.ussd_handler), name='survey_interrogation'),
    re_path(r'^surveys/(?P<survey_title>.+)/$', views.survey_detail, name='survey_detail'),
    re_path(r'^surveys/$', views.surveys_list, name='surveys_list'),
]
