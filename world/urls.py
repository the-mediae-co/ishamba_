from django.urls import re_path
from django.contrib.auth.decorators import login_required

from world.views import BordersForLocationView, BordersSearch

urlpatterns = [
    re_path(
        r'^borders_for_location$',
        login_required(BordersForLocationView.as_view()),
        name='borders_for_location'
    ),
    re_path(
        r'^search/?$',
        login_required(BordersSearch.as_view()),
        name='search'
    ),
]
