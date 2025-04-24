from django.conf import re_path
from django.contrib.auth.decorators import login_required

from . import views

app_name = 'exports'

urlpatterns = [
    re_path(r'^$', login_required(views.ExportView.as_view()), name='list'),
    re_path(r'^customers/', login_required(views.CustomerExportCreateView.as_view()), name='customers'),
    re_path(r'^incoming-messages/', login_required(views.IncomingSMSExportCreateView.as_view()), name='incoming-messages'),
    re_path('^maps/$', login_required(views.MapExportView.as_view()), name='maps_list'),
    re_path(r'^maps/create/$', login_required(views.MapExportCreateView.as_view()), name='maps_create'),
]
