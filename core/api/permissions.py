from rest_framework import permissions


class IPWhitelistPermission(permissions.BasePermission):
    """
    Global permission check allowing only whitelisted IPs.
    """
    WHITELISTED_IPS = []

    def has_permission(self, request, view):
        ip_addr = request.META['REMOTE_ADDR']
        return ip_addr in self.WHITELISTED_IPS
