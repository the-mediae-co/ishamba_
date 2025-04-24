import math
import os
import phonenumbers
import sys
from typing import Dict, Union
from collections.abc import Iterable
from functools import lru_cache

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, Point, MultiPolygon
from django.db.models import Value
from django.db.models import QuerySet
from django.db.models.functions import Concat
from django.utils.translation import gettext_lazy as _

from world.models import Border, BorderLevelName

KENYA = Border.objects.none()
UGANDA = Border.objects.none()
ZAMBIA = Border.objects.none()

def point_in_supported_area(point: Point) -> bool:
    """ Return True if the given point is in Kenya, Uganda, or Zambia"""
    global KENYA
    global UGANDA
    global ZAMBIA
    if not point:
        return False
    if not KENYA:
        KENYA = Border.objects.get(name="Kenya", level=0)
    if not UGANDA:
        UGANDA = Border.objects.get(name="Uganda", level=0)
    if not ZAMBIA:
        ZAMBIA = Border.objects.get(name="Zambia", level=0)
    return KENYA.border.contains(point) | UGANDA.border.contains(point) | ZAMBIA.border.contains(point)


def process_counties_kml() -> Dict[str, GEOSGeometry]:
    source = DataSource(f'{os.path.dirname(__file__)}/data/counties.kml')
    return {feature['Name'].value: MultiPolygon(GEOSGeometry(feature.geom.geos))
            for feature in source[0]}


def get_border_for_location(point: Point, level: int) -> Border:
    try:
        border = Border.objects.only('pk').get(level=level, border__intersects=point)
    except Border.DoesNotExist:
        cutoff = settings.WORLD_COUNTY_DISTANCE_CUTOFF
        # .first will return None if no matches found
        border = (Border.objects.filter(level=level)
                  .annotate(distance=Distance('border', point))
                  .filter(distance__lt=cutoff.m)
                  .order_by('distance')
                  .first())
    return border


def is_valid_border_for_location(border: Border, point: Point) -> bool:
    """Border is considered valid if its border shape contains the location, or if the location is
    within the pre-configured cutoff distance to the border. Since both the border and point are
    already loaded into memory, we avoid going to SQL, and perform all computations in Python library.
    This however requires converting distance from degrees to meters.
    """
    if border.border.contains(point):
        return True
    distance = border.border.distance(point)  # distance in degrees
    distance *= math.pi / 180 * 6.371e6  # distance in meters along the great circle
    return distance < settings.WORLD_COUNTY_DISTANCE_CUTOFF.m


@lru_cache(maxsize=0 if "pytest" in sys.modules else 5)
def _get_country_for_iso2(iso2: str) -> Border:
    """
    A utility function that returns the country associated with an iso2 country code.
    This method uses an lru_cacue to prevent excessive DB hits.
    """
    try:
        country_name = BorderLevelName.objects.get(iso2=iso2, level=0).country
        country = Border.objects.get(country=country_name, level=0)
        return country
    except (Border.DoesNotExist, BorderLevelName.DoesNotExist):
        raise ValueError(_('Not a country that we operate in.'))


def get_country_for_phone(phone: Union[str, phonenumbers.PhoneNumber]) -> Border:
    try:
        if isinstance(phone, str):
            phone = phonenumbers.parse(phone)
    except phonenumbers.phonenumberutil.NumberParseException:
        raise ValueError('Invalid phone number.')
    if not phonenumbers.is_valid_number(phone):
        raise ValueError('Invalid phone number.')

    country_iso2 = phonenumbers.phonenumberutil.region_code_for_number(phone)
    return _get_country_for_iso2(country_iso2)


@lru_cache(maxsize=0 if "pytest" in sys.modules else 5)
def get_phone_country_code_for_country(country: Border) -> int:
    try:
        iso2 = BorderLevelName.objects.get(country=country.name, level=0).iso2
        return phonenumbers.country_code_for_region(iso2)
    except (BorderLevelName.DoesNotExist, BorderLevelName.MultipleObjectsReturned):
        return None


@lru_cache(maxsize=0 if "pytest" in sys.modules else 50)
def _get_border_choices(level: int) -> list[int, str]:
    """
    Passing in a queryset to a field's choices gets evaluated at compile time and
    can cause problems. By passing in a method name, the expression evaluation
    happens at the time of the view being called, which works both in testing and production.
    """
    try:
        list = [(c.pk, c.name) for c in Border.objects.filter(level=level).order_by('name')]
    except RuntimeError as e:
        # When run under pytest, database access may not yet be available, which throws a RuntimeError
        list = []
    return list


def get_border0_choices() -> list[int, str]:
    return _get_border_choices(0)


def get_border1_choices() -> list[int, str]:
    return _get_border_choices(1)


def get_border2_choices() -> list[int, str]:
    return _get_border_choices(2)


def get_border3_choices() -> list[int, str]:
    return _get_border_choices(3)


def _get_border_set(selector) -> QuerySet:
    # Make sure these are iterables of Border objects
    if selector is None or selector == [None]:
        return Border.objects.none()

    if isinstance(selector, QuerySet):
        return selector

    if isinstance(selector, Border):
        return Border.objects.filter(pk=selector.pk)

    if isinstance(selector, str):
        return Border.objects.filter(pk=int(selector))

    if isinstance(selector, list):
        if all(isinstance(x, (str, int)) for x in selector):
            return Border.objects.filter(pk__in=selector)
        else:
            raise ValueError(f"selector must be iterable of Borders or Border PK's not: {type(selector)}")


def process_border_ajax_menus(selected_border0s: Iterable | Border, selected_border1s: Iterable | Border,
                              selected_border2s: Iterable | Border, selected_border3s: Iterable | Border,
                              request: dict, response: dict = None) -> dict:
    # Set defaults
    change_border0_options = False
    change_border1_options = False
    change_border2_options = False
    change_border3_options = False
    border0_options = list(Border.objects.filter(level=0).values_list('name', flat=True))
    border1_options = []
    border2_options = []
    border3_options = []
    enable_border0 = True
    enable_border1 = False
    enable_border2 = False
    enable_border3 = False
    changed_field = None

    # Make sure these are iterables of Border objects
    selected_border0s = _get_border_set(selected_border0s)
    selected_border1s = _get_border_set(selected_border1s)
    selected_border2s = _get_border_set(selected_border2s)
    selected_border3s = _get_border_set(selected_border3s)

    # Extract the form details from the ajax post
    if request:
        changed_field = request.get('changed_field')

    if changed_field is None or changed_field == 'border0':
        if selected_border0s:
            border1_qs = Border.objects.filter(parent_id__in=selected_border0s, level=1) \
                .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
            border1_options = [{'id': c[0], 'name': c[1]} for c in border1_qs
                .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
            # border1_qs and border1_options should already be set above
            if border1_qs and selected_border1s:
                border2_qs = Border.objects.filter(parent_id__in=selected_border1s, level=2) \
                    .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
                border2_options = [{'id': c[0], 'name': c[1]} for c in border2_qs
                                   .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
                if border2_qs:
                    border3_options = list(Border.objects.filter(parent__in=border2_qs, level=3)
                                           .values('id', 'name').order_by('parent__name', 'name'))
                else:
                    border3_options = []
            else:
                border2_options = []
                border3_options = []
        else:
            border1_options = []
            border2_options = []
            border3_options = []

        # Remove selected_borders that are not in selected border0s.
        # I.e. if a border0 was removed, remove its corresponding border1s, border2s and border3s.
        if selected_border1s or selected_border2s or selected_border3s:
            if selected_border0s:
                selected_border1s = selected_border1s.filter(parent__in=selected_border0s)
                selected_border2s = selected_border2s.filter(parent__in=selected_border1s)
                selected_border3s = selected_border3s.filter(parent__in=selected_border2s)
            else:
                selected_border1s = Border.objects.none()
                selected_border2s = Border.objects.none()
                selected_border3s = Border.objects.none()

        change_border1_options = change_border2_options = change_border3_options = True

        if not (request.get('is_multiselect') == 'true' or request.get('is_multiselect') is True):
            enable_border2 = enable_border3 = False

    if changed_field == 'border1' or selected_border1s:
        if selected_border1s:
            border2_qs = Border.objects.filter(parent_id__in=selected_border1s, level=2) \
                .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
            border2_options = [{'id': c[0], 'name': c[1]} for c in border2_qs
                               .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
            if border2_qs:
                border3_qs = Border.objects.filter(parent_id__in=border2_qs, level=3) \
                    .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
                border3_options = [{'id': c[0], 'name': c[1]} for c in border3_qs
                    .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
        else:
            border2_options = []
            border3_options = []

        # Remove selected_border2s that are not in selected border1s.
        # I.e. if a border1 was removed, remove its corresponding border2s and border3s.
        if selected_border2s or selected_border3s:
            if selected_border1s:
                selected_border2s = selected_border2s.filter(parent__in=selected_border1s)
                selected_border3s = selected_border3s.filter(parent__in=selected_border2s)
            else:
                selected_border2s = Border.objects.none()
                selected_border3s = Border.objects.none()

        if changed_field == 'border1':
            change_border2_options = change_border3_options = True

        if not (request.get('is_multiselect') == 'true' or request.get('is_multiselect') is True):
            enable_border3 = False

    if changed_field == 'border2' or selected_border2s:
        # This filter returns an empty list if selected_border2s is empty
        if selected_border2s:
            border3_qs = Border.objects.filter(parent_id__in=selected_border2s, level=3) \
                .annotate(hierarchy_name=Concat('name', Value(' ('), 'parent__name', Value(')')))
            border3_options = [{'id': c[0], 'name': c[1]} for c in border3_qs
                               .values_list('id', 'hierarchy_name').order_by('parent__name', 'name')]
        else:
            border3_options = []
            selected_border3s = Border.objects.none()

        # Remove selected_border3s that are not in selected border2s.
        # I.e. if a border2 was removed, remove its corresponding border3s.
        if selected_border3s:
            if selected_border2s:
                selected_border3s = selected_border3s.filter(parent__in=selected_border2s)
            else:
                selected_border3s = Border.objects.none()

        if changed_field == 'border2':
            change_border3_options = True

    if selected_border0s:
        enable_border1 = True

    if selected_border0s and selected_border1s:
        enable_border2 = True

    if selected_border0s and selected_border1s and selected_border2s:
        enable_border3 = True

    if response is None:
        response = {}

    # If one or more countries are selected, use the names of those countries' administrative boundaries as the labels
    if selected_border0s:
        for level in range(0, 4):
            label_names = BorderLevelName.objects.filter(country__in=selected_border0s.values_list('name', flat=True),
                                                         level=level).distinct('name').values_list('name', flat=True)
            response.update({f'border{level}_label': ' / '.join(label_names)})

    response.update({
        'change_border1_options': change_border1_options,
        'change_border2_options': change_border2_options,
        'change_border3_options': change_border3_options,
        'border0_options': border0_options,
        'border1_options': border1_options,
        'border2_options': border2_options,
        'border3_options': border3_options,
        'enable_border0': True,
        'enable_border1': enable_border1,
        'enable_border2': enable_border2,
        'enable_border3': enable_border3,
        'selected_border0s': list(selected_border0s.values_list('pk', flat=True).order_by('name')) if selected_border0s else [],
        'selected_border1s': list(selected_border1s.values_list('pk', flat=True).order_by('name')) if selected_border1s else [],
        'selected_border2s': list(selected_border2s.values_list('pk', flat=True).order_by('name')) if selected_border2s else [],
        'selected_border3s': list(selected_border3s.values_list('pk', flat=True).order_by('name')) if selected_border3s else [],
    })

    return response
