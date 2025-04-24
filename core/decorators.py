from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden

from ipware import get_client_ip

from core.logger import log


def ip_authorisation(authorised_ips):
    """ Used in url authorization to fnforce that a request must come from an
        iterable of authorised_ips. Disable with settings.IP_AUTHORIZATION.
    """
    def bound_ip_authorisation(view):
        @wraps(view)
        def inner(request, *args, **kwargs):
            client_ip, is_routable = get_client_ip(request)
            if client_ip in authorised_ips or not getattr(settings, 'IP_AUTHORIZATION', True):
                return view(request, *args, **kwargs)
            else:
                log.warning('Access attempt from non-whitelisted IP: {}'.format(client_ip))
                return HttpResponseForbidden()
        return inner
    return bound_ip_authorisation


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()
