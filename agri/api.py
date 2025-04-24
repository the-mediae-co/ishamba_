from django.db.models import Count, Q
from ninja import  Router
from ninja.security import django_auth

from agri.models import Commodity
from agri.schema import CommoditySchema
from callcenters.models import CallCenterOperator

router = Router(
    auth=django_auth,
    tags=['agri'],
)


@router.get("/commodities/", response=list[CommoditySchema])
def value_chains(request) -> list[Commodity]:
    callcenters = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id')
    current_callcenter = callcenters.first()
    return Commodity.objects.annotate(
        call_center_tips_count=Count('tips', filter=Q(tips__call_center_id=current_callcenter.call_center_id))
    )


@router.get("/commodities/{int:commodity_id}/", response=CommoditySchema)
def retrieve_commodity(request, commodity_id: int) -> Commodity:
    callcenters = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id')
    current_callcenter = callcenters.first()
    return Commodity.objects.annotate(
        call_center_tips_count=Count('tips', filter=Q(tips__call_center_id=current_callcenter.call_center_id))
    ).get(id=commodity_id)


@router.post("/commodities/{int:commodity_id}/enable_tips/", response=CommoditySchema)
def enable_commodity_tips(request, commodity_id: int) -> Commodity:
    comm = Commodity.objects.get(id=commodity_id)
    comm.tips_enabled = True
    comm.save()
    return comm


@router.post("/commodities/{int:commodity_id}/disable_tips/", response=CommoditySchema)
def disable_commodity_tips(request, commodity_id: int) -> Commodity:
    comm = Commodity.objects.get(id=commodity_id)
    comm.tips_enabled = False
    comm.save()
    return comm

