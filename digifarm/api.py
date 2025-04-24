from typing import Union

from django.conf import settings
from ninja import  Router
from ninja.errors import HttpError
from ninja.security import HttpBearer

from agri.models import Commodity
from agri.schema import CommoditySchema
from digifarm.schema import BorderSchema, FarmerBulkSyncResponse, FarmerBulkSyncSchema, MetaDataSchema
from digifarm.utils import sync_farmers
from world.models import Border, get_county_names_and_ids


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if token == settings.DIGIFARM_AUTHENTICATION_SECRET:
            return token


router = Router(
    auth=AuthBearer(),
    tags=['digifarm'],
)

@router.get("/value_chains/", response=list[CommoditySchema])
def value_chains(request) -> list[Commodity]:
    return Commodity.objects.all()


@router.get("/metadata/")
def metadata(request) -> MetaDataSchema:
    return MetaDataSchema()


@router.get("/counties/", response=list[BorderSchema])
def counties(request) -> list[dict[str, Union[int, str]]]:
    return [{'id': item[1], 'name': item[0]} for item in get_county_names_and_ids()]


@router.get("/{int:county_id}/sub_counties/", response=list[BorderSchema])
def sub_counties(request, county_id: int) -> list[Border]:
    return Border.objects.filter(country='Kenya', level=2, parent=county_id)


@router.get("/{int:sub_county_id}/wards/", response=list[BorderSchema])
def wards(request, sub_county_id: int) -> list[Border]:
    return Border.objects.filter(country='Kenya', level=3, parent=sub_county_id)


@router.post("/farmers/sync/", response=FarmerBulkSyncResponse)
def digifarm_sync_farmers(request, data: FarmerBulkSyncSchema) -> FarmerBulkSyncResponse:
    if settings.ENABLE_DIGIFARM_INTEGRATION:
        return sync_farmers(data.farmers)
    else:
        raise HttpError(404, "Sync disabled")
