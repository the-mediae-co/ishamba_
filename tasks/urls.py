from django.urls import re_path
from django.contrib.auth.decorators import login_required

from tasks import views

urlpatterns = [
    # Task views
    re_path(
        r'^$',
        login_required(views.TaskTableView.as_view()),
        name='task_list'),
    re_path(
        r'^update/(?P<pk>\d+)/$',
        login_required(views.TaskUpdateView.as_view()),
        name='task_update'),
    re_path(
        r'^cannot_contact_customer/(?P<pk>\d+)/$',
        login_required(views.CannotContactCustomerView.as_view()),
        name='cannot_contact_customer'),
    re_path(
        r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$',
        login_required(views.TaskSMSReplyView.as_view()),
        name='task_reply')
]
