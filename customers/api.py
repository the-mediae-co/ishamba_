from typing import Any

from django.http import HttpRequest
from django.db import transaction

from ninja import Query, Router
from ninja.security import django_auth

from callcenters.models import CallCenterOperator
from customers.models import Customer, CustomerCommodity
from customers.schema import CustomerFetchResponse, CustomerFilters


router = Router(
    auth=django_auth,
    tags=['customers'],
)


@router.get('customers/', response=CustomerFetchResponse)
def fetch_customers(request: HttpRequest, customerFilters: CustomerFilters = Query(...)) -> dict[str, Any]:
    search = Customer.search.sort('-id')
    if customerFilters.tips_commodity:
        search = search.filter('term', tips_commodities=customerFilters.tips_commodity)
    if customerFilters.subscribed_to_tips:
        search = search.filter('exists', field='tips_commodities')
    callcenters = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id')
    current_callcenter = callcenters.first()
    if current_callcenter:
        search = search.filter('term', call_center=current_callcenter.call_center_id)
    response = search[(customerFilters.page - 1) * customerFilters.size:(customerFilters.page) * customerFilters.size].execute()
    items = [hit.to_dict() for hit in response.hits]
    return {
        'items': items,
        'total_count': response.hits.total.value,
        'page': customerFilters.page,
        'size': customerFilters.size
    }


@router.post("/commodities/{int:commodity_id}/")
def add_customers_to_freemium_tips(request, commodity_id: int, data: list[str]):
    to_create = []

    customers = Customer.objects.filter(id__in=data)

    for cus_id in customers.values_list('id', flat=True):
        to_create.append(
            CustomerCommodity(commodity_id=commodity_id, customer_id=cus_id)
        )

    CustomerCommodity.objects.bulk_create(to_create, ignore_conflicts=True)
    CustomerCommodity.objects.filter(customer_id__in=data, commodity_id=commodity_id).update(primary=True)
    CustomerCommodity.objects.filter(customer_id__in=data).exclude(commodity_id=commodity_id).update(primary=False)
    def on_commit():
        Customer.index_many(customers)
        Customer.es.indices.refresh()
    transaction.on_commit(on_commit)
