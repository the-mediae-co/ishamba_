# Generated by Django 4.1.8 on 2023-05-06 12:15

from django.db import migrations
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django_tenants.utils import tenant_context


def add_permission(apps, schema_editor):
    """
        Creates an 'exporters_group' with permissions to export Tasks and Customers
    """
    Client = apps.get_model('core', 'Client')  # NOQA
    Task = apps.get_model('tasks', 'Task')  # NOQA
    Customer = apps.get_model('customers', 'Customer')  # NOQA

    for client in Client.objects.all():
        # Since this migration is central to the platform, we put it in the 'core' app which
        # is in the 'public' schema, and as such, we need to loop through tenants manually.
        with tenant_context(client):
            task_type = ContentType.objects.get_for_model(Task)
            customer_type = ContentType.objects.get_for_model(Customer)
            task_export_perm = Permission.objects.get(codename='export', content_type=task_type)
            customer_export_perm = Permission.objects.get(codename='export', content_type=customer_type)
            exporters_group, created = Group.objects.get_or_create(name='Content exporters')
            if created:
                exporters_group.permissions.add(task_export_perm)
                exporters_group.permissions.add(customer_export_perm)


def remove_permission(apps, schema_editor):
    """
        Reverses the migration
    """
    Client = apps.get_model('core', 'Client')  # NOQA
    for client in Client.objects.all():
        # Since this migration is central to the platform, we put it in the 'core' app which
        # is in the 'public' schema, and as such, we need to loop through tenants manually.
        with tenant_context(client):
            Group.objects.filter(name='Content exporters').delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_remove_client_domain_url"),
        ("customers", "0119_add_export_permission"),
        ("tasks", "0019_add_export_permission"),
    ]

    operations = [
        migrations.RunPython(add_permission, reverse_code=remove_permission),
    ]
