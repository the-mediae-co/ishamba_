import cachetools
from django.contrib.gis.db import models
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from core.decorators import classproperty
from django.utils.translation import gettext_lazy as _


class Border(models.Model):
    country = models.CharField(max_length=120)                      # Name of the country that this area is in
    level = models.SmallIntegerField()          # The administrative level of this area. E.g. county, ward, etc.
    parent = models.ForeignKey('self', null=True,
                               related_name='subdivisions',
                               on_delete=models.CASCADE)            # The id (pk) of the administrative area this is in
    name = models.CharField(max_length=120, blank=True, null=True)  # The name (local)
    name_en = models.CharField(max_length=120)                      # The name (english)
    border = models.MultiPolygonField(geography=True, srid=4326)    # The multipolygon geoGRAPHY (not geometry)

    class Meta:
        verbose_name_plural = 'Borders'
        ordering = ['name']
        indexes = [
            models.Index(fields=['country'], name='border_country_idx'),
            models.Index(fields=['level'], name='border_level_idx'),
            models.Index(fields=['name'], name='border_name_idx'),
            models.Index(fields=['name_en'], name='border_name_en_idx'),
        ]

    def __str__(self):
        name = f"{self.name}"
        if self.parent:
            name += f" ({self.parent.name})"
        return name

    @classproperty
    def kenya_counties(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Kenya", level=1)

    @classproperty
    def kenya_subcounties(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Kenya", level=2).order_by('parent__name')

    @classproperty
    def kenya_wards(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Kenya", level=3).order_by('parent__name')

    @classproperty
    def uganda_regions(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Uganda", level=1)

    @classproperty
    def uganda_districts(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Uganda", level=2).order_by('parent__name')

    @classproperty
    def uganda_counties(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Uganda", level=3).order_by('parent__name')

    @classproperty
    def zambia_provinces(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Zambia", level=1)

    @classproperty
    def zambia_districts(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Zambia", level=2).order_by('parent__name')

    @classproperty
    def zambia_constituencies(cls) -> 'QuerySet[Border]':
        return Border.objects.filter(country="Zambia", level=3).order_by('parent__name')

    @property
    def phone_number_prefix(self) -> str:
        if self.country == 'Kenya':
            return '+254'
        if self.country == 'Uganda':
            return '+256'
        if self.country == 'Zambia':
            return '+260'
        return '+1'

    @property
    def currency(self) -> str:
        if self.country == 'Kenya':
            return 'ksh'
        if self.country == 'Uganda':
            return 'ugx'
        if self.country == 'Zambia':
            return 'zmw'
        return 'usd'


class BorderLevelName(models.Model):
    iso = models.SmallIntegerField(blank=True, null=True)
    iso2 = models.CharField(max_length=2)
    iso3 = models.CharField(max_length=3)
    level = models.SmallIntegerField()
    country = models.CharField(max_length=120)
    name = models.CharField(max_length=120, blank=True, null=True)
    name_en = models.CharField(max_length=120)

    class Meta:
        verbose_name_plural = 'Border level names'

    def __str__(self):
        return ', '.join([self.country, self.name])


# exposed so it can be cleared from tests
COUNTY_CACHE = cachetools.Cache(maxsize=1)


class County(models.Model):
    """DEPRECATED"""
    name = models.CharField(max_length=255, unique=True)
    boundary = models.GeometryField(geography=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Counties'
        # managed = False

    def __str__(self):
        # This class should not be used anymore
        raise ImproperlyConfigured('world.County is no longer used')
        # return self.name


@cachetools.cached(COUNTY_CACHE)
def get_county_names_and_ids() -> list[tuple[str, int]]:
    return Border.kenya_counties.values_list('name', 'id')
