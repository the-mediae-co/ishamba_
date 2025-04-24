# 'widgets' because this is what django-import-export calls them.
#  Their function is to act as the transformers for a field, cleaning
#  data on import and rendering it again on export. We mostly have to write
#  them because the data we are receiving is not only denormalised but also
#  contains a lot of crap.
#
#  <https://django-import-export.readthedocs.org/en/latest/api_widgets.html>
import re
import sentry_sdk
from itertools import chain

# from django.apps import apps
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.utils.timezone import make_aware

import phonenumbers
from dateutil.parser import parse as dateutil_parse
from fuzzywuzzy import process
from import_export import widgets

from core.logger import log
from agri.models import Region
from core.constants import LANGUAGES
from customers.models import CustomerPhone
from sms.utils import clean_sms_text
from world.utils import point_in_supported_area
from world.models import Border, BorderLevelName


class ForeignKeyLookupWidget(widgets.Widget):
    """ Similar to import-export's ForeignKeyWidget but allows us to look up
        Foreign Key links using a specifed field rather than assuming primary
        key.

        Requires extra arguments:
            - model: the class to which the field is related.
            - lookup_field: the field to do the lookup on; should be able to
                            return a unique object. The lookup will be done on
                            this field with the value being cleaned.
    """

    def __init__(self, model, lookup_field, required=True, *args, **kwargs):
        self.model = model
        self.lookup_field = lookup_field
        self.required = required
        super().__init__(*args, **kwargs)

    def clean(self, value, row=None, *args, **kwargs):
        cleaned_value = super().clean(value, row, *args, **kwargs)
        lookup_params = {self.lookup_field: cleaned_value}
        try:
            obj = self.model._default_manager.get(**lookup_params)
        except self.model.DoesNotExist:
            if not self.required:
                return None
            msg = "Field references a model: {0}.{1} with value '{2}' that does not exist."
            raise ValueError(msg.format(self.model._meta.app_label,
                                        self.model._meta.object_name,
                                        cleaned_value))
        return obj

    def render(self, value, obj=None):
        """ Return the lookup value requested, not just the PK
        as ForeignKeyWidget would do.
        """
        if value is None:
            return ""
        return getattr(value, self.lookup_field)


class FuzzyLookupWidget(ForeignKeyLookupWidget):
    """ Subclasses ForeignKeyLookupWidget with fuzzy-string matching.

        As the database doesn't offer this, we achieve the same result somewhat
        inefficiently by loading in all values first, getting the top fuzzy
        match from the list, then performing an exact lookup using the top hit.
    """

    def clean(self, value, row=None, *args, **kwargs):

        choices = self.model.objects.values_list(self.lookup_field, flat=True)
        score_cutoff = settings.IMPORTER_FUZZY_MATCH_SCORE_CUTOFF
        best_match, score = process.extractOne(value, choices)
        if score < score_cutoff:
            msg = ("Field references a model: {app}.{model} with value "
                   "'{value}'. "
                   "Best fuzzy match is '{best_match}', score {score} "
                   "(threshold is {score_cutoff})")
            raise ValueError(msg.format(app=self.model._meta.app_label,
                                        model=self.model._meta.object_name,
                                        value=value,
                                        best_match=best_match,
                                        score=score,
                                        score_cutoff=score_cutoff))
        if score != 100:
            # We passed the threshold test, but log this anyway.
            msg = ("Import could not find exact match for '{value}'. "
                   "Fuzzy match selected {best_match} with score {score}.")
            log.info(msg.format(value=value,
                                best_match=best_match,
                                score=score))
        return super().clean(best_match, row, *args, **kwargs)


class DateutilDateTimeWidget(widgets.Widget):
    """
    A datetime widget which uses the dateutils parser
    to be receiving dates in about 4 different formats: sometimes with
    nanoseconds which are unsupported, sometimes with a time - sometimes-without,
    etc, we need this widget to provide a normalised datetime value.
    """

    def __init__(self, format=None):
        if format is None:
            format = "%Y-%m-%d %H:%M:%S"
        self.format = format

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        # Parse string input with dateutil
        parsed_date = dateutil_parse(value)  # unaware
        # Make the returned datetime timezone-aware for use with Django
        value = make_aware(parsed_date)
        return value

    def render(self, value, obj=None):
        """ To render, we take the first format as this is preferred. """
        return value.strftime(self.format)


class GSMTextWidget(widgets.CharWidget):
    """ Extends CharWidget to provide additional GSM character set whitelisting
    """

    def clean(self, value, row=None, *args, **kwargs):
        try:
            value = clean_sms_text(value)
        except ValidationError as e:
            raise ValueError(' '.join(chain(*e.message_dict.values())))

        return value


class PhoneNumbersWidget(widgets.ForeignKeyWidget):

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return value
        error_msg = '{} is not a valid list of phone numbers'.format(value)
        number_strings = [s.strip() for s in value.split(',')]
        phones = []
        for n_str in number_strings:
            if not n_str:
                continue
            try:
                number = phonenumbers.parse(n_str, None)
            except phonenumbers.NumberParseException:
                raise ValueError(error_msg)

            if not phonenumbers.is_valid_number(number):
                raise ValueError(error_msg)

            formatted_number = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)

            if CustomerPhone.objects.filter(number=formatted_number).exists():
                raise ValueError(f"{formatted_number} already belongs to an existing customer")

            phones.append(formatted_number)

        # Return an array of strings which can be passed into a queryset with phones__numbers__in=[]
        return phones

    def render(self, value, obj=None):
        return ','.join(value)


class LocationWidget(widgets.Widget):

    def clean(self, value, row=None, *args, **kwargs):

        if not value:
            return None

        # split on space or comma (with optional trailing space)
        lon, lat = re.split(' +|, ?', value)
        point = Point(float(lon), float(lat))

        if not point_in_supported_area(point):
            raise ValueError('Location is not in a supported area')

        return point

    def render(self, value, obj=None):
        return value


class PreferredLanguageWidget(widgets.Widget):

    def clean(self, value, row=None, *args, **kwargs):
        """
        Provides validation based on the LANGUAGES enum
        Implementation adapted from `django.db.models.fields.Field.validate()`.
        """
        value = super().clean(value, row, *args, **kwargs)

        for option_key, option_value in LANGUAGES.choices:
            if isinstance(option_value, (list, tuple)):
                # This is an optgroup, so look inside the group for options.
                for optgroup_key, optgroup_value in option_value:
                    if value == optgroup_key:
                        return value
            elif value == option_key:
                return value
            elif value == option_value:
                return option_key

        raise ValueError(f"Value {value} is not a valid choice.")


class BorderWidget(widgets.Widget):
    def __init__(self, level: int, *args, **kwargs):
        self.country_name: str = None  # noqa
        self.level: int = level
        self.level_name: str = None  # noqa
        super().__init__(*args, **kwargs)

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return
        # If we have not been initialized with a country yet...
        if not self.country_name:
            error_msg = f"Unknown country for administrative unit {value}. Please either use the country-specific " \
                        f"column header names for the geo administrative units or fill in the country " \
                        f"column of the first (non-header) row and move the country column to the left of other " \
                        f"administrative unit columns."
            if self.level == 0:
                try:
                    # If we are a country level widget, set self.country on first appearance of a value
                    if isinstance(value, int) or (isinstance(value, str) and value.isnumeric()):
                        # Must be a pk. Validate that it's a country in the database
                        unit = Border.objects.get(level=self.level, pk=value)
                        self.country_name = unit.name
                    else:
                        # Assume the value is the name of a country
                        unit = Border.objects.get(country=value, level=self.level)
                        self.country_name = unit.name
                except Border.MultipleObjectsReturned:
                    # If multiple border items are returned, we can't disambiguate
                    raise ValueError(error_msg)
                except Border.DoesNotExist:
                    raise ValueError(error_msg)
            else:
                raise ValueError(error_msg)

        error_msg = f"{value} is not a valid {self.level_name} (level {self.level}) in {self.country_name}"
        try:
            if isinstance(value, int) or (isinstance(value, str) and value.isnumeric()):
                # Must be a pk. Validate that it's the right country and level
                unit = Border.objects.get(country=self.country_name, level=self.level, pk=value)
            else:
                # Assume the value is the name of a border unit at this level
                # To disambiguate some entries, we also need to know the border item's parent
                parent_identifier = ""

                # If this widget is not representing a country, find its parent
                if self.level == 1:
                    parent_identifier = self.country_name
                elif row and self.level > 1:
                    try:
                        # Extract the name of the administrative border level
                        parent_borderlevelname = BorderLevelName.objects.get(country=self.country_name, level=self.level - 1)
                        level_name = parent_borderlevelname.name.lower()
                        if level_name in row:
                            parent_identifier = row.get(level_name)
                    except BorderLevelName.DoesNotExist:
                        pass

                if self.level == 0:
                    # If a country, it has no parent
                    unit = Border.objects.get(country=self.country_name,
                                              level=self.level,
                                              name=value)
                else:
                    # Otherwise, use the parent to disambiguate.
                    if isinstance(parent_identifier, int) or (isinstance(parent_identifier, str) and parent_identifier.isnumeric()):
                        unit = Border.objects.get(country=self.country_name,
                                                  level=self.level,
                                                  parent__id=parent_identifier,
                                                  name=value)
                    else:
                        unit = Border.objects.get(country=self.country_name,
                                                  level=self.level,
                                                  parent__name=parent_identifier,
                                                  name=value)
        except Border.MultipleObjectsReturned:
            # If multiple border items are returned, we can't disambiguate. This would only happen
            # if the value is not a pk. Note that the world.Border database can have multiple
            # units with the same name within the same parent. This appears to be due to quality
            # issues in the maps themselves. Ideally these would be fixed when they are found.
            # We return the first unit and raise a Sentry message so the administrator can investigate.
            sentry_sdk.capture_message(f"Duplicate administrative borders detected: "
                                       f"{value} in {self.country_name}, level {self.level}")
            if isinstance(parent_identifier, int) or (isinstance(parent_identifier, str) and parent_identifier.isnumeric()):
                unit = Border.objects.filter(country=self.country_name,
                                             level=self.level,
                                             parent__id=parent_identifier,
                                             name=value).first()
            else:
                unit = Border.objects.filter(country=self.country_name,
                                             level=self.level,
                                             parent__name=parent_identifier,
                                             name=value).first()
        except Border.DoesNotExist:
            raise ValueError(error_msg)
        return unit

    def render(self, value, obj=None):
        if isinstance(value, Border):
            return value.name
        else:
            return value


class AgriculturalRegionWidget(widgets.Widget):

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return
        error_msg = f"{value} is not a valid agricultural region"
        agricultural_region = None
        try:
            if isinstance(value, str):
                if value.isnumeric():
                    # Must be a pk. Validate that it's the right country and level
                    agricultural_region = Region.objects.get(pk=value)
                else:
                    # Assume the value is the name of a boundary unit at this level
                    agricultural_region = Region.objects.get(name=value)
            elif isinstance(value, int):
                # Must be a pk. Validate that it's the right country and level
                agricultural_region = Region.objects.get(pk=value)
        except Region.DoesNotExist:
            raise ValueError(error_msg)
        return agricultural_region

    def render(self, value, obj=None):
        return value.name
