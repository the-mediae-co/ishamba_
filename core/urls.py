from django.urls import re_path
from django.contrib.auth.decorators import login_required

import core.views
from core.widgets import AuthSelect2View
import sms.views

urlpatterns = [
    re_path(r'^$', login_required(core.views.ManagementView.as_view()), name='core_management'),
    re_path(r'^metrics/$', login_required(core.views.MetricsView.as_view()), name='core_management_metrics'),
    re_path(r'^nps/$', login_required(core.views.NPSView.as_view()), name='core_management_nps'),
    re_path(r'^charts/membership/$', login_required(core.views.MembershipRateChartView.as_view()), name='core_management_membership_rate'),
    re_path(r'^charts/calls/$', login_required(core.views.CallRateChartView.as_view()), name='core_management_call_rate'),
    re_path(r'^bulk_sms/$', login_required(sms.views.CustomerFilterFormView.as_view()), name='core_management_customer_filter'),
    re_path(r'^bulk_sms/compose/$', login_required(sms.views.BulkOutgoingSMSCreateView.as_view()), name='core_management_customer_bulk_compose'),
    re_path(r'^new_customers_chart/', login_required(core.views.new_customers_chart), name='new_customers_chart'),
    re_path(r'^nps_histogram_chart/', login_required(core.views.nps_histogram_chart), name='nps_histogram_chart'),
    re_path(r'^task_metrics_chart/', login_required(core.views.task_metrics_chart), name='task_metrics_chart'),
    re_path(r'^select2/', login_required(core.widgets.AuthSelect2View.as_view()), name='auth_select2_view'),
]
