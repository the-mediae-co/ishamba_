from django.urls import path
from django.contrib.auth.decorators import login_required

from callcenters.views import CallCentresIndexFormView


urlpatterns = [
    path('', login_required(CallCentresIndexFormView.as_view()),name='call_centers_index'),
]
