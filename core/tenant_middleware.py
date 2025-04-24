from django.conf import settings
from django.db import connection
from django_tenants.middleware import TenantMainMiddleware


class DebuggingTenantMiddleware(TenantMainMiddleware):
    """
    When DEBUG=True and the request comes via an ngrok.io tunnel, force the main tenant schema
    """
    def get_tenant(self, domain_model, hostname):
        if settings.DEBUG and hostname.endswith('ngrok-free.app'):
            # When debugging via ngrok, return the default tenant
            domain = domain_model.objects.get(is_primary=True)
            return domain.tenant
        return super(DebuggingTenantMiddleware, self).get_tenant(domain_model, hostname)
