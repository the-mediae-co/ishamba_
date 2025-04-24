
from datetime import datetime, timedelta
from typing import Any
from callcenters.models import CallCenterOperator
from ninja import Router
from ninja.security import django_auth

from tips.models import TipSeason, Tip, TipTranslation
from tips.schema import TipCreateSchema, TipSchema, TipSeasonSchema, TipsUploadSchema
from world.models import Border


router = Router(tags=["advisory"], auth=[django_auth])


@router.get("tips/", response=list[TipSchema])
def fetch_tips(request, commodity_id: int) -> list[dict[str, Any]]:
    callcenters = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id')
    current_callcenter = callcenters.first()
    search = Tip.search.filter('term', commodity_id=commodity_id).sort('delay_days')
    if current_callcenter:
        search = search.filter('term', call_center_id=current_callcenter.call_center_id)
    response = search[0:10000].execute()
    return [hit.to_dict() for hit in response.hits]


@router.get("tips/{int:tip_id}/", response=TipSchema)
def retrieve_tip(request, tip_id: int) -> dict[str, Any]:
    return Tip.from_index(tip_id)


@router.patch("tips/{int:tip_id}/", response=TipSchema)
def update_tip(request, tip_id: int, data: TipCreateSchema) -> dict[str, Any]:

    tip = Tip.objects.get(id=tip_id)

    if data.delay_days:
        tip.delay = timedelta(days=data.delay_days)
    for translation in data.translations:
        TipTranslation.objects.update_or_create(tip=tip, language=translation.language, defaults={'text': translation.text})
    tip.save()
    updated_data = Tip.index_one(tip)
    return updated_data

@router.delete("tips/{int:tip_id}/")
def archive_tip(request, tip_id: int, data: TipCreateSchema) -> None:
    tip = Tip.objects.get(id=tip_id)
    tip.legacy = True
    tip.save()
    updated_data = Tip.delete_one(tip)
    return updated_data


@router.post("tips/")
def upload_tips(request, data: TipsUploadSchema) -> None:
    """
    """
    callcenters = CallCenterOperator.objects.filter(operator=request.user, active=True).order_by('-current', '-id')
    current_callcenter = callcenters.first()
    tips = []
    for tip_data in data.tips:
        tip_data_dict = tip_data.dict()
        translations_data = tip_data_dict.pop('translations', [])
        tip_data_dict['delay'] = timedelta(days=tip_data_dict.pop('delay_days'))
        if current_callcenter:
            tip_data_dict['call_center_id'] = current_callcenter.call_center_id
        tip, created = Tip.objects.get_or_create(**tip_data_dict, commodity_id=data.commodity_id, legacy=False)
        for translation_data in translations_data:
            print(translation_data)
            TipTranslation.objects.create(tip=tip, **translation_data)
        tips.append(tip)
    Tip.index_many(tips)


@router.get("tip_seasons/", response=list[TipSeasonSchema])
def fetch_tip_seasons(request, commodity_id: int) -> list[dict[str, Any]]:
    search = TipSeason.search.filter('term', commodity_id=commodity_id).sort('start_date')
    response = search[0:10000].execute()
    return [hit.to_dict() for hit in response.hits]


@router.post("tip_seasons/{int:commodity_id}/")
def upload_seasons(request, commodity_id: int, data: list[list[str]]) -> list[list[str]]:
    errors = []
    for season_item in data:
        border2_name = season_item[1]
        border3_name = season_item[2]
        planting_date_str = season_item[3]
        try:
            planting_date = datetime.strptime(planting_date_str, '%d/%m/%Y')
            border3 = Border.objects.get(level=3, name__iexact=border3_name, parent__name__iexact=border2_name)
            tip_season, _ = TipSeason.objects.get_or_create(commodity_id=commodity_id, start_date=planting_date)
            customer_filters = tip_season.customer_filters or {}
            border3_ids = customer_filters.get('border3', [])
            border3_ids.append(border3.id)
            customer_filters['border3'] = list(set(border3_ids))
            tip_season.customer_filters = customer_filters
            tip_season.save()

        except Border.DoesNotExist:
            errors.append(season_item)
        except Exception as e:
            errors.append(season_item)
    return errors
