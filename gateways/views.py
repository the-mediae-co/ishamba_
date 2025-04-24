from logging import getLogger

from django.http import HttpResponse, HttpResponseForbidden
from django.views.generic import View
from django.conf import settings

from .forms import BaseDeliveryReportForm
from .signals import delivery_report_received
from ipware import get_client_ip

logger = getLogger(__name__)


class IPAuthorizationMixin(object):
    def dispatch(self, request, *args, **kwargs):
        """
        Dispatch overridden to apply IP based authorization to the view.
        """
        client_ip, is_routable = get_client_ip(request)

        if (client_ip not in settings.AUTHORIZED_IPS and
                getattr(settings, 'IP_AUTHORIZATION', True)):
            logger.warning(
                'Access attempt from non-whitelisted IP: {}'.format(client_ip))
            return HttpResponseForbidden()
        return super(IPAuthorizationMixin, self).dispatch(request, *args,
                                                          **kwargs)


class BaseDeliveryReportView(IPAuthorizationMixin, View):
    """ Base view for delivery report callback delivered via POST request.
    """
    http_method_names = ['post']  # limit to POST requests
    gateway = None
    form = BaseDeliveryReportForm

    def post(self, request, *args, **kwargs):
        form = self.form(request.POST)

        if not form.is_valid():
            logger.warning('Delivery report form invalid: %s',
                           dict(list(form.errors.items())),
                           extra={'post_req': request.POST})
            return HttpResponse('')  # return a blank response to the gateway

        # If the delivery was successful, only log if we are debugging
        if 'Success' in request.POST.get('status'):
            logger.debug('Delivery report received: %s', request.POST)
        # otherwise if not successful, log the failure as informational
        else:
            logger.info('Delivery report received: %s', request.POST)

        # send a signal with the gateway id and status so that that individual
        # Django projects can define how delivery reports are processed.
        delivery_report_received.send(
            sender=self.__class__,
            **form.cleaned_data
        )

        return HttpResponse('')  # return a blank response to the gateway
