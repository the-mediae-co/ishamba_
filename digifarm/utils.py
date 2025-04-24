from datetime import timedelta
from typing import Optional

from core.logger import log
from core.utils.datetime import _get_current_date
from core.constants import LANGUAGES
from customers.models import CropHistory, Customer, CustomerPhone
from digifarm.schema import FarmerBulkSyncResponse, FarmerSubscriptionSchema, FarmerSyncErrorResponse, FarmerSyncSchema, FarmerSyncSuccessResponse
from digifarm.tasks import send_digifarm_bulk_sms
from subscriptions.models import Subscription, SubscriptionType


def sync_farmer(farmer_data: FarmerSyncSchema) -> tuple[FarmerSyncSuccessResponse, bool]:
    customer = Customer.objects.filter(digifarm_farmer_id=farmer_data.digifarm_farmer_id).first()
    subscription_info = farmer_data.subscription
    onboarded = False
    if not customer:
        try:
            customer_phone: Optional[CustomerPhone] = CustomerPhone.objects.get(
                gdpr_hash=farmer_data.phone_number_hash
            )
            customer = customer_phone.customer
            if customer.currently_subscribed and not customer.digifarm_farmer_id:
                raise ValueError("Already subscribed to Ishamba")
        except CustomerPhone.DoesNotExist:
            customer_phone = None
            customer, onboarded = Customer.objects.get_or_create(
                phone_number_hash=farmer_data.phone_number_hash,
                defaults=dict(
                    digifarm_farmer_id=farmer_data.digifarm_farmer_id,
                    name=farmer_data.name or "",
                    dob=farmer_data.dob,
                    sex=farmer_data.sex or "",
                    postal_address=farmer_data.postal_address or "",
                    postal_code=farmer_data.postal_code or "",
                    phone_type=farmer_data.phone_type or "",
                    preferred_language=farmer_data.preferred_language or LANGUAGES.ENGLISH,
                )
            )
    customer.commodities.add(*[v.commodity for v in farmer_data.value_chains])
    for value_chain in farmer_data.value_chains:
        if value_chain.date_planted:
            CropHistory.objects.get_or_create(
                customer=customer,
                commodity_id=value_chain.commodity,
                defaults={'date_planted': value_chain.date_planted}
            )
    sub_type, created = SubscriptionType.objects.get_or_create(
        external_reference=f'digifarm_{subscription_info.subscription_type}'
    )

    expiry_date = subscription_info.expiry_date

    if not expiry_date:
        expiry_date = today + timedelta(days=180)

    today = _get_current_date()

    subscription, updated = Subscription.objects.update_or_create(
        type=sub_type,
        customer=customer,
        defaults={
            'start_date': today,
            'end_date': expiry_date,
            'external_reference': subscription_info.reference
        }
    )

    customer.border3_id = farmer_data.ward
    customer.border2_id = customer.border3.parent_id
    customer.border1_id = customer.border2.parent_id
    customer.border0_id = customer.border1.parent_id
    customer.save()
    return FarmerSyncSuccessResponse(
        digifarm_farmer_id=customer.digifarm_farmer_id,
        ishamba_farmer_id=customer.pk,
        phone_number_hash=customer.phone_number_hash,
        subscription=FarmerSubscriptionSchema(
            subscription_type=subscription_info.subscription_type,
            expiry_date=subscription.end_date,
            reference=subscription.external_reference,
            ishamba_id=subscription.pk
        )
    ), onboarded


def sync_farmers(farmers_data: list[FarmerSyncSchema]) -> FarmerBulkSyncResponse:
    response = FarmerBulkSyncResponse(synced=[], errors=[])
    onboarding_message_recipients = []
    for farmer_data in farmers_data:
        try:
            synced_farmer_data, onboarded = sync_farmer(farmer_data)
            response.synced.append(
                synced_farmer_data
            )
            # if onboarded:
            onboarding_message_recipients.append(synced_farmer_data.digifarm_farmer_id)
        except Exception as e:
            log.exception(e)
            response.errors.append(
                FarmerSyncErrorResponse(
                    error_detail="Could not sync the farmer",
                    digifarm_farmer_id=farmer_data.digifarm_farmer_id,
                    phone_number_hash=farmer_data.phone_number_hash
                )
            )
    if onboarding_message_recipients:
        send_digifarm_bulk_sms.delay(onboarding_message_recipients, 'digifarm_sync')
    return response
