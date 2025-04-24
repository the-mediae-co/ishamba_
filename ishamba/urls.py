from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.urls import re_path
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.contrib.gis import admin
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from gateways.africastalking.views import ATIncomingSMSView

from ishamba.api import api
from core.views import HomeTemplateView

admin.autodiscover()


urlpatterns = [
    re_path(r'^new_ishamba/.*?', login_required(TemplateView.as_view(template_name='index.html')), name='new_ishamba'),
    re_path(r'^$', HomeTemplateView.as_view(), name='home'),
    re_path(
        r'^accounts/login/$',
        auth_views.LoginView.as_view(template_name='account/login.html'),
        name='login'
    ),
    re_path(
        r'^accounts/logout/$',
        auth_views.LogoutView.as_view(template_name='account/logout.html'),
        name='logout'),

    re_path(r'^customers/', include('customers.urls')),
    re_path(r'^calls_centers/', include('callcenters.urls')),
    re_path(r'^calls/', include('calls.urls')),
    re_path(r'^tasks/', include('tasks.urls')),

    re_path(r'^sms/incoming_sms_callback/$',
        csrf_exempt(ATIncomingSMSView.as_view()),
        name='sms_api_callback'),

    re_path(r'^gateways/', include('gateways.urls')),

    re_path(r'^weather/', include('weather.urls')),
    re_path(r'^world/', include('world.urls')),
    re_path(r'^management/', include('core.urls')),
    re_path(r'^offers/', include('payments.urls.offers')),

    re_path(r'^activity/', include('actstream.urls')),

    # the urls will have names with the following pattern
    # apiVersion:app:view_name
    # e.g apiv1:customers:join
    re_path(r'^api/v1/', include('ishamba.apiv1', namespace='apiv1')),
    re_path(r'^api/', api.urls),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    re_path(r'^admin/', admin.site.urls),
    re_path(r'^ussd2/', include('interrogation.urls')),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    import debug_toolbar
    urlpatterns += [re_path(r'^__debug__/', include(debug_toolbar.urls))]
