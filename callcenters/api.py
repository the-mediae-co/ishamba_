
from ninja import Router
from ninja.security import django_auth

from callcenters.models import CallCenterOperator
from callcenters.schema import CallCenterOperatorSchema


router = Router(tags=["callcenters"], auth=django_auth)


@router.get("/", response=list[CallCenterOperatorSchema])
def list_call_centers(request) -> list[CallCenterOperator]:
    return CallCenterOperator.objects.filter(operator=request.user)


@router.get("/{int:callcenter_id}/", response=CallCenterOperatorSchema)
def retrieve_call_center(request, callcenter_id: int) -> CallCenterOperator:
    return CallCenterOperator.objects.filter(operator=request.user).get(id=callcenter_id)


@router.post("/{int:call_center_id}/set_current/", response=CallCenterOperatorSchema)
def update_callcenter_role(request, call_center_id: int) -> CallCenterOperator:
    call_center_role = CallCenterOperator.objects.get(operator=request.user, call_center_id=call_center_id)
    call_center_role.current = True
    call_center_role.save()
    CallCenterOperator.objects.filter(operator=request.user).exclude(id=call_center_role.id).update(current=False)
    return call_center_role
