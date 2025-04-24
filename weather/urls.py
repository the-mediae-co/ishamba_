from django.urls import re_path

from . import views

app_name = 'weather'

urlpatterns = [
    re_path(r'^upload$', views.CountyForecastUploadView.as_view(), name='county_forecast_upload'),
]
