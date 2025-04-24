import codecs
import csv

from django import forms
from django.db.models import Q

from customers.models import CustomerCategory
from world.models import Border

from .models import CountyForecast


class CountyForecastForm(forms.ModelForm):
    start = forms.DateField()
    end = forms.DateField()

    class Meta:
        model = CountyForecast
        fields = ['county', 'text', 'category']

    def clean(self):
        data = super().clean()
        start = data.get('start')
        end = data.get('end')
        if start and end and start >= end:
            raise forms.ValidationError("Start date should be before end date")
        return data


class CountyForecastUploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        forecast_file = self.cleaned_data["file"]
        forecasts = csv.reader(codecs.iterdecode(forecast_file, "utf-8"))
        self.forecast_forms = []

        mandatory_columns = ["county", "text", "start", "end"]
        optional_columns = ["category", "premium_only"]
        valid_columns = mandatory_columns + optional_columns

        headers = next(forecasts)
        if headers[0].strip().lower() not in valid_columns:
            raise forms.ValidationError(
                f"The first row of the input file must contain the column headers: {mandatory_columns} "
                f"and optionally: {optional_columns}"
            )

        row_count = 1
        errs = []
        fields = []
        for col in headers:
            cleaned_col = col.strip().lower()
            if cleaned_col not in valid_columns:
                errs.append(col)
            else:
                fields.append(cleaned_col)

        if errs:
            raise forms.ValidationError(
                f"Unknown columns: {errs}. Valid choices are {valid_columns}"
            )

        for forecast in forecasts:
            row_count += 1
            if len(fields) != len(forecast):
                raise forms.ValidationError(
                    f'Invalid row: Number of columns ({len(forecast)}) does not match number of headers ({len(fields)}).'
                )

            data = dict(list(zip(fields, forecast)))

            for field in mandatory_columns:
                value = data.get(field, None)
                if value is None or len(value) == 0:
                    raise forms.ValidationError(
                        f"The {field} field cannot be empty on row {row_count} of imported spreadsheet"
                    )

            county = data["county"]
            if isinstance(county, int) or county.isnumeric():
                # If a number was given, assume it's the county's id
                county_filter = Q(id=county)
            else:
                # ...otherwise assume it's the category name
                county_filter = Q(name__iexact=county)
            try:
                data["county"] = Border.objects.get(
                    county_filter, country="Kenya", level=1,
                ).pk
            except Border.DoesNotExist:
                raise forms.ValidationError(
                    "The county {} does not exist.".format(data["county"])
                )

            if "category" in data:
                category = data["category"]
                if isinstance(category, int) or category.isnumeric():
                    # If a number was given, assume it's the category's id
                    category_filter = Q(id=category)
                else:
                    # ...otherwise assume it's the category name
                    category_filter = Q(name__iexact=category)

                try:
                    data["category"] = CustomerCategory.objects.get(category_filter).pk
                except CustomerCategory.DoesNotExist:
                    raise forms.ValidationError(
                        "The category {} does not exist.".format(data["category"])
                    )

            premium_only = True  # Default value
            if "premium_only" in data:
                premium_only = data.get("premium_only")
                if isinstance(premium_only, int):
                    premium_only = (
                        premium_only == 1
                    )  # True if premium_only == 1, else False
                elif isinstance(premium_only, str):
                    premium_only = premium_only.strip().lower() in ("true", "1")
                else:
                    raise forms.ValidationError(
                        f"Unknown value {premium_only} for premium_only field. Valid choices are: True, False, 1 or 0."
                    )

            forecast_form = CountyForecastForm(data)
            if not forecast_form.is_valid():
                raise forms.ValidationError(list(forecast_form.errors.values())[0])
            else:
                self.forecast_forms.append(forecast_form)

        return forecast_file

    def save(self, user):
        to_create = []

        for forecast_form in self.forecast_forms:
            forecast = forecast_form.save(commit=False)
            forecast.dates = [forecast_form.cleaned_data['start'], forecast_form.cleaned_data['end']]
            forecast.last_editor_id = user.id
            forecast.creator_id = user.id
            to_create.append(forecast)

        CountyForecast.objects.bulk_create(to_create)
