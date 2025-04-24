from typing import Dict, List, NamedTuple

from django.conf import settings
from django.db import IntegrityError, connection, migrations

from django_tenants.utils import get_tenant_model


class TK(NamedTuple):
    name: str
    text: str
    keywords: List[str] = ()
    create_task: bool = False


static_data: Dict[str, List[TK]] = {
    'ishamba': [
        TK(settings.SMS_EMPTY_MESSAGE_RESPONSE,
           "Sorry we did not get your message correctly. Kindly resend your question or call 0711082606",
           ['']),
    ],
    'ichef': [
        TK(settings.SMS_EMPTY_MESSAGE_RESPONSE,
           "Sorry we did not get your message correctly. Kindly resend your question or call 0711082606",
           ['']),
    ]
}

def create(tk: TK, template_model, keyword_model):
    template, created = template_model.objects.get_or_create(name=tk.name)
    template.text = tk.text
    template.create_task = tk.create_task
    template.protected = True
    template.save()

    for kw in tk.keywords:
        try:
            keyword_model.objects.get_or_create(response=template, keyword=kw)
        except IntegrityError:
            keyword = keyword_model.objects.get(keyword=kw)
            raise Exception(
                f'Keyword {kw} is already associated with the different template ({keyword.response.name}). '
                'You must manually remove this keyword before re-attempting the migration.')


def get_static_data() -> List[TK]:
    schema = connection.schema_name
    if schema in static_data:
        return static_data[schema]

    # use iShamba templates as meta-templates for the default schema templates
    tenant_model = get_tenant_model()
    tenant = tenant_model.objects.get(schema_name=schema)
    tenant_name = 'iShamba' if not tenant.name or tenant.name == 'test' else tenant.name
    return [
        template._replace(text=template.text.replace('iShamba', tenant_name))
        for template in static_data['ishamba']
    ]


def populate_default_smsresponses(apps, schema_editor):
    # populate the models manually, since import statements pull the latest
    # version, rather than the version current at the time of this migration
    sms_response_template = apps.get_model('sms', 'SMSResponseTemplate')
    sms_response_keyword = apps.get_model('sms', 'SMSResponseKeyword')

    for tk in get_static_data():
        create(tk, template_model=sms_response_template, keyword_model=sms_response_keyword)


def remove_default_smsresponses(apps, schema_editor):
    # remove the models manually, since import statements pull the latest
    # version, rather than the version current at the time of this migration
    sms_response_template = apps.get_model('sms', 'SMSResponseTemplate')

    sms_response_template.objects.filter(name__in=[tk.name for tk in get_static_data()]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('sms', '0054_add_data_request_type'),
    ]

    operations = [
        migrations.RunPython(populate_default_smsresponses, reverse_code=remove_default_smsresponses),
    ]
