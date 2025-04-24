from core.api.permissions import IPWhitelistPermission
from django.conf import settings


class CustomerJoinPermission(IPWhitelistPermission):
    """
    Whitelist permission for ishamba.com's IP
    """
    if not settings.DEBUG:
        WHITELISTED_IPS = ['46.43.3.10', '52.208.21.31']
    else:
        WHITELISTED_IPS = ['localhost', '127.0.0.1']


class ChatbotTestingPermission(IPWhitelistPermission):
    def has_permission(self, request, view):
        return True
