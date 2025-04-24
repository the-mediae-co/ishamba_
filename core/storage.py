import os

from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.exceptions import SuspiciousOperation
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.utils._os import safe_join

from django_s3_storage.storage import S3Storage


# This project used to depend on django-tenant-schemas, however that project
# appears to be unsupported so we switched to django-tenants. That does
# not support TenantStorageMixin, so we copied the raw implementation
# from here: https://github.com/bernardopires/django-tenant-schemas/blob/master/tenant_schemas/storage.py
class TenantStorageMixin(object):
    """
    Mixin that can be combined with other Storage backends to colocate media
    for all tenants in distinct subdirectories.

    Using rewriting rules at the reverse proxy we can determine which content
    gets served up, while any code interactions will account for the multiple
    tenancy of the project.
    """
    def path(self, name):
        """
        Look for files in subdirectory of MEDIA_ROOT using the tenant's
        domain_url value as the specifier.
        """
        if name is None:
            name = ''
        try:
            location = safe_join(self.location, connection.tenant.domain_url)
        except AttributeError:
            location = self.location
        try:
            path = safe_join(location, name)
        except ValueError:
            raise SuspiciousOperation(
                "Attempted access to '%s' denied." % name)
        return os.path.normpath(path)


class TenantFileSystemStorage(TenantStorageMixin, FileSystemStorage):
    """
    Implementation that extends core Django's FileSystemStorage.
    """


class TenantStaticFilesStorage(TenantStorageMixin, StaticFilesStorage):
    """
    Implementation that extends core Django's StaticFilesStorage.
    """


class S3TenantStorage(TenantStorageMixin, S3Storage):

    def _get_key_name(self, name):
        from core.models import Client, Domain
        client = Client.objects.get(schema_name=connection.tenant.schema_name)
        domain = client.domains.get(is_primary=True)
        tenant_name = os.path.join(domain.domain, client.name, name)
        return super()._get_key_name(tenant_name)
