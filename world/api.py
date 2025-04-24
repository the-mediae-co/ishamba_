from ninja import  Query, Router
from ninja.security import django_auth

from world.models import BorderLevelName, Border
from world.schema import BorderLevelSchema, BorderLevelFilters, BorderSchema, BorderFilters


router = Router(
    auth=django_auth,
    tags=['world'],
)

@router.get("/border_levels/", response=list[BorderLevelSchema])
def border_levels(request, filters: BorderLevelFilters = Query(...)) -> list[BorderLevelName]:
    qs = BorderLevelName.objects.all()
    if filters.country:
        qs = qs.filter(country__iexact=filters.country)
    return qs


@router.get("/borders/", response=list[BorderSchema])
def borders(request, filters: BorderFilters = Query(...)) -> list[Border]:
    qs = Border.objects.all()
    if filters.country:
        qs = qs.filter(country__iexact=filters.country)
    if filters.level:
        qs = qs.filter(level=filters.level)
    if filters.parent:
        qs = qs.filter(parent_id=filters.parent)
    if filters.search:
        qs = qs.filter(name__icontains=filters.search)
    return qs[:5]
