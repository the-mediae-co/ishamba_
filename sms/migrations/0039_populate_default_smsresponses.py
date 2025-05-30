# Generated by Django 2.2.16 on 2020-09-14 14:46
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
        TK(settings.SMS_JOIN,
           "Thank you for opting to JOIN iShamba. To sign up, kindly SMS your Name, County, "
           "Ward, Primary School near your farm, Land size, Crop/Livestock farmed to 21606",
           ['JOIN']),
        TK(settings.SMS_STOP,
           "Asante for contacting iShamba, you have requested for our messages "
           "to stop. To rejoin the service, please SMS JOIN to {shortcode}.",
           ['STOP', 'UNSUBSCRIBE', 'END', 'OFF']),
        TK(settings.SMS_INACTIVE_CUSTOMER_REJOIN,
           "Welcome back to iShamba! An agent will call you shortly to confirm your registration details. "
           "The service will be restored immediately.",
           create_task=True),
        TK(settings.SMS_ACTIVE_CUSTOMER_JOIN,
           "You are already a member of iShamba! To reach our experts call "
           "{call_centre} or SMS your questions to {shortcode}. Calls charged at "
           "local rate, SMS cost 1KSh per SMS."),
        TK(settings.SMS_INACTIVE_CUSTOMER_STOP,
           "Asante for contacting iShamba. This number is not "
           "currently receiving messages. Please SMS JOIN to {shortcode} to "
           "subscribe. Good luck shaping up your shamba."),
        TK(settings.SMS_REGISTRATION_COMPLETED_SWAHILI,
           "Karibu kwa iShamba! kuzungumza na wataalamu wetu, tupigie simu kupitia "
           "{call_centre} au utume ujumbe kwa {shortcode}. Jiunge na mpango wa "
           "PREMIUM kwa manufaa zaidi.\n"
           "Kujiunga na PREMIUM, nenda kwa Mpesa, Lipa na Mpesa, Buy Goods and "
           "Services, Till number {till_number}. Kulipia Miezi 4 lipa KES 300, miezi 6 "
           "KES 450 & mwaka KES 800"),
        TK(settings.SMS_REGISTRATION_COMPLETED_ENGLISH,
           "Welcome to iShamba! To speak to our farm experts, call us on "
           "{call_centre} or SMS your farm question on {shortcode}. Join our "
           "PREMIUM service for more farming benefits.\n"
           "To join PREMIUM, go to Mpesa, Lipa na Mpesa, Buy Goods & Services, Till "
           "number {till_number}. For 4 months pay KES 300, 6 months KES 450 & 1 year "
           "KES 800"),
        TK(settings.SMS_SUBSCRIPTION_REMINDER,
           "Your iShamba credit will run out on {short_end_date}. Please MPesa "
           "{month_price} for 1 month/{year_price} for 1 year to Till number "
           "{till_number}. Call iShamba {call_centre} or Text {shortcode}"),
        TK(settings.SMS_SUBSCRIPTION_EXPIRED,
           "Your iShamba credit has now run out. Please MPesa {month_price} for "
           "one month or {year_price} for one year, to Till number {till_number} "
           "to re-join iShamba."),
        TK(settings.SMS_LAPSED_CUSTOMER_REMINDER,
           "Hello from iShamba! To reach our call centre of farming experts "
           "MPesa {month_price} to Till number {till_number}, we'll send you "
           "many tips to help you shape up your shamba!"),
        TK(settings.SMS_LAPSED_CUSTOMER_REJOINS,
           "Welcome back to iShamba! You can reach the call centre on "
           "{call_centre}, or text any questions to {shortcode}. SMS cost 5KSH "
           "per SMS, and calls are at a local rate."),
        TK(settings.SMS_PAYMENT_RECEIVED_RESPONSE,
           "Ahsante na karibu kwa iShamba! Call us on {call_centre} or SMS "
           "{shortcode} (SMS cost 5KSH to send/calls charged at a local rate). "
           "Your membership will expire on {long_end_date}"),
        TK(settings.SMS_INSUFFICIENT_PAYMENT_RESPONSE,
           "iShamba membership costs {month_price} for one month or {year_price} "
           "for one year. Please transfer to MPesa till number {till_number}. "
           "Asante, iShamba."),
        TK(settings.SMS_UNSPECIFIED_PAYMENT_ERROR,
           "Pole, iShamba is experiencing some difficulties with your payment. "
           "One of our iShamba agronomy experts will call you in the next 48 "
           "hours to discuss this."),
        TK(settings.SMS_VOUCHER_OFFER_EXPIRED,
           "This voucher offer has expired."),
        TK(settings.SMS_VOUCHER_ALREADY_USED,
           "This single-use voucher has already been used."),
        TK(settings.SMS_VOUCHER_ALREADY_USED_BY_YOU,
           "This voucher ({voucher_duration} months) has already been applied to "
           "your account. You cannot use this voucher more than once."),
        TK(settings.SMS_FREE_MONTHS_VOUCHER_ACCEPTED,
           "Ahsante na karibu kwa iShamba! We have added {voucher_duration} free "
           "months to your subscription. It is now valid until {long_end_date})"),
        TK(settings.SMS_UNSUPPORTED_REGION,
           "Sorry, iShamba is not available in your country. We'll let you know "
           "when we get to you, good luck shaping up your shamba!"),
        TK(settings.SMS_SIGNATURE,
           "call the call centre on {call_centre} for more information"),
        TK(settings.SMS_CANNOT_CONTACT_CUSTOMER,
           "We tried to call 3 times but we could not reach you. "
           "Kindly SMS your Name, Ward, County, Land size, Crop/Livestock farmed to 21606 to sign up for iShamba."),
        TK('call_centre_temporarily_closed',
           "Hello, thank you for contacting iShamba! The iShamba call centre is temporarily closed. "
           "We will get back to you as soon as possible.")
    ],
    'ichef': [
        TK(settings.SMS_JOIN,
           "Asante kwa kutuma ujumbe kwa iChef. We will call you soon to "
           "register you on iChef.",
           ['JOIN']),
        TK(settings.SMS_STOP,
           "Thank you for contacting iChef, you have requested for our "
           "messages to stop. Please SMS JOIN to {shortcode} to re-join "
           "the service.",
           ['STOP', 'UNSUBSCRIBE', 'END', 'OFF']),
        TK(settings.SMS_INACTIVE_CUSTOMER_REJOIN,
           "Welcome back to iChef! An agent will call you shortly to confirm your registration details. "
           "The service will be restored immediately.",
           create_task=True),
        TK(settings.SMS_ACTIVE_CUSTOMER_JOIN,
           "You are already subscribed to iChef! Call us on {call_centre} "
           "or SMS questions to {shortcode}. Calls charged at local rate, "
           "SMS cost KSh 5 per SMS"),
        TK(settings.SMS_INACTIVE_CUSTOMER_STOP,
           "Thank you for contacting iChef. This number is not "
           "currently receiving messages. Please SMS JOIN to {shortcode} "
           "to subscribe. Thank you."),
        TK(settings.SMS_REGISTRATION_COMPLETED_SWAHILI,
           "Karibu kwa iChef! Utapokea ujumbe kwa njia ya SMS. Kuzungumza "
           "nasi, tupigie simu kupitia {call_centre} au utume ujumbe kwa "
           "{shortcode}.\n"
           "Asante kwa kujiunga na iChef. Utapokea ujumbe kwa njia ya "
           "SMS. Ukiwa na swali, tupigie simu kupitia {call_centre} au utume ujumbe kwa "
           "{shortcode}."),
        TK(settings.SMS_REGISTRATION_COMPLETED_ENGLISH,
           "Welcome to iChef! To speak our call centre agents, call us on "
           "{call_centre} or SMS your question on {shortcode}."),
        TK(settings.SMS_SUBSCRIPTION_REMINDER,
           "Hello! To reach our call centre MPesa {month_price} to Till"
           "number {till_number}, we'll send you many tips to help you "
           "shape up your cooking!"),
        TK(settings.SMS_SUBSCRIPTION_EXPIRED,
           "Your iChef subscription has now run out. Please MPesa "
           "{month_price} for one month or {year_price} for one year, to "
           "Till number {till_number} to re-join iChef"),
        TK(settings.SMS_LAPSED_CUSTOMER_REMINDER,
           "Your iChef subscription will expire on {short_end_date}. "
           "Please Mpesa {year_price} for 1 year to Till number "
           "{till_number}. Call {call_centre} or SMS {shortcode}"),
        TK(settings.SMS_LAPSED_CUSTOMER_REJOINS,
           "Welcome back to iChef! You can reach the call centre on "
           "{call_centre} or send questions to {shortcode}. SMS cost 5KSH "
           "per SMS, and calls are at a local rate."),
        TK(settings.SMS_PAYMENT_RECEIVED_RESPONSE,
           "Asante na karibu kwa iChef! Call us on {call_centre} or SMS "
           "{shortcode} (SMS cost 5KSH to send/calls charged at a local "
           "rate). Your membership will expire on {long_end_date}."),
        TK(settings.SMS_INSUFFICIENT_PAYMENT_RESPONSE,
           "iChef membership costs {month_price} for one month or "
           "{year_price} for one year. Please transfer to MPesa till "
           "number {till_number}. Thank"),
        TK(settings.SMS_UNSPECIFIED_PAYMENT_ERROR,
           "Sorry, iChef is experiencing some difficulties with your "
           "payment. One of our iChef team members will call you in the "
           "next 48 hours to discuss this."),
        TK(settings.SMS_VOUCHER_OFFER_EXPIRED,
           "This voucher offer has expired."),
        TK(settings.SMS_VOUCHER_ALREADY_USED,
           "This single-use voucher has already been used."),
        TK(settings.SMS_VOUCHER_ALREADY_USED_BY_YOU,
           "This voucher has already been used"),
        TK(settings.SMS_FREE_MONTHS_VOUCHER_ACCEPTED,
           "Asante na karibu kwa iChef! We have added {voucher_duration} "
           "free months to your subscription. It is now valid until "
           "{long_end_date}"),
        TK(settings.SMS_UNSUPPORTED_REGION,
           "Sorry, iChef is not available in your country. We'll let you "
           "know when we get to you."),
        TK(settings.SMS_SIGNATURE,
           "Call the call centre on {call_centre} for more information."),
        TK(settings.SMS_CANNOT_CONTACT_CUSTOMER,
           "We tried to call 3 times but we could not reach you. Please "
           "send us an SMS when you are available and we will call you "
           "back"),
        TK('call_centre_temporarily_closed',
           "Hello, thank you for contacting iChef! The iChef call centre is temporarily closed. "
           "We will get back to you as soon as possible.")
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
        ('sms', '0038_smsresponsetemplate_protected'),
    ]

    operations = [
        migrations.RunPython(populate_default_smsresponses, reverse_code=remove_default_smsresponses),
    ]
