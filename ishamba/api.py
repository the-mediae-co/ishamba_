from django.http import HttpRequest, HttpResponse
from django.urls import path

from ninja import NinjaAPI
from ninja.errors import ValidationError

from agri.api import router as agri_router
from digifarm.api import router as digifarm_router
from callcenters.api import router as callcenters_router
from tips.api import router as tips_router
from world.api import router as world_router
from sms.api import router as sms_router
from customers.api import router as customers_router

__all__ = ['api']

api = NinjaAPI(
    version="1.0.0",
    title="Ishamba API",
    urls_namespace='api',
    docs_url='/docs/',
    csrf=True
)

@api.exception_handler(ValidationError)
def api_validation_errors(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    """ Override the default validation error handler to return a status of 400 instead of 422 """
    return api.create_response(request, {"errors": exc.errors}, status=400)

api.add_router('digifarm', digifarm_router)
api.add_router('callcenters', callcenters_router)
api.add_router('advisory', tips_router)
api.add_router('agri', agri_router)
api.add_router('world', world_router)
api.add_router('sms', sms_router)
api.add_router('crm', customers_router)
