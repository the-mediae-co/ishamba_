import json

from django.contrib import admin
from djangoql.admin import DjangoQLSearchMixin
from djangoql.schema import DjangoQLSchema, StrField
from django.utils.html import format_html

from import_export.admin import ImportExportMixin
from phonenumber_field.modelfields import PhoneNumberField

from core.admin import TimestampedBaseAdmin, TimestampedBaseAdminMixin
from core.importer import resources

from world.admin import iShambaMapWidget
from world.models import Border, BorderLevelName

from . import forms, models


@admin.register(models.CustomerBank)
class CustomerBankAdmin(TimestampedBaseAdmin):
    pass


@admin.register(models.CustomerCategory)
class CustomerCategoryAdmin(TimestampedBaseAdmin):
    search_fields = ('name',)


@admin.register(models.CustomerCoop)
class CustomerCoopAdmin(TimestampedBaseAdmin):
    pass


@admin.register(models.CustomerSavingsCoop)
class CustomerSavingsCoopAdmin(TimestampedBaseAdmin):
    pass


class CustomerMapWidget(iShambaMapWidget):
    def __init__(self, customer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.customer = customer

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if self.customer:
            context.update({
                'search_geom': None,
                'enableLeafletEditing': True,
                'customer.id': self.customer.id,
                'border2_label': BorderLevelName.objects.get(country=self.customer.border0, level=2).name,
                'border2_name': self.customer.border2.name if self.customer.border2 else "",
                'border2_geom': self.customer.border2.border.json if self.customer.border2 else None,
                'border2_centroid': self.customer.border2.border.centroid.json  if self.customer.border2 else None,
                'border3_label': BorderLevelName.objects.get(country=self.customer.border0, level=3).name,
                'border3_name': self.customer.border3.name if self.customer.border3 else "",
                'border3_geom': self.customer.border3.border.json if self.customer.border3 else None,
                'border3_centroid': self.customer.border3.border.centroid.json if self.customer.border3 else None,
            })
            if self.customer.location:
                gps_string = dict(zip(('lng', 'lat'), self.customer.location.coords))
                context['customerGPS'] = json.dumps(gps_string)

            if self.customer.border2:
                context.update({
                    'border2_name': self.customer.border2.name,
                    'border2_geom': self.customer.border2.border.json,
                    'border2_centroid': self.customer.border2.border.centroid.json,
                })
            if self.customer.border3:
                context.update({
                    'border3_name': self.customer.border3.name,
                    'border3_geom': self.customer.border3.border.json,
                    'border3_centroid': self.customer.border3.border.centroid.json,
                })
        return context


class CustomerAnswerInline(TimestampedBaseAdminMixin, admin.TabularInline):
    fields = ('question', 'text',)
    form = forms.CustomerQuestionAnswerForm
    formset = forms.CustomerQuestionAnswerFormset
    model = models.CustomerQuestionAnswer


class CustomerQLSchema(DjangoQLSchema):

    def get_field_cls(self, field):
        if isinstance(field, PhoneNumberField):
            return StrField
        return super().get_field_cls(field)


class CustomerQLSearchMixin(DjangoQLSearchMixin):

    def get_search_results(self, request, queryset, search_term):
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        use_distinct = True
        return qs, use_distinct


class CustomerPhoneInline(admin.TabularInline):
    fields = ('number', 'is_main',)
    model = models.CustomerPhone
    extra = 0


class CustomerSurveyInline(admin.TabularInline):
    readonly_fields = ('survey_title', 'data_source', '_responses', 'is_finished','finished_at')
    exclude = ('responses', 'creator_id', 'last_editor_id')
    model = models.CustomerSurvey
    extra = 0

    @admin.display(description="Responses")
    def _responses(self, obj: models.CustomerSurvey):
        json_responses = obj.responses
        html_str = "<div style='height: 200px; overflow: scroll'>"
        for question, response in json_responses.items():
            html_str += f"<li>{question}: {response}</li>"
        html_str += "</div>"
        return format_html(html_str)


@admin.register(models.Customer)
class CustomerAdmin(CustomerQLSearchMixin, ImportExportMixin, TimestampedBaseAdmin):
    djangoql_schema = CustomerQLSchema
    # We need to import and export different sets of fields, so instead
    # of specifying a general purpose resource_class here, we specify
    # separate import and export resources in the methods below
    list_display = ('id', 'name', 'border0', 'border1', 'border2', 'border3')
    exclude = ('creator_id', 'last_editor_id', 'has_bank', 'has_cooperative',
               'has_savings_coop', 'has_farmer_group', 'farmer_group', 'bank',
               'savings_coop', 'cooperative', 'heard_about_us')

    inlines = [
        CustomerPhoneInline,
        CustomerAnswerInline,
        CustomerSurveyInline
    ]
    autocomplete_fields = ['border1', 'border2', 'border3']

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if form:
            form.base_fields['location'].widget = CustomerMapWidget(obj)
            form.base_fields['border0'].label = 'Country'
            form.base_fields['border0'].queryset = Border.objects.filter(level=0)
            if obj:
                country_name = obj.border0.name
                for level in range(1, 4):
                    level_name = BorderLevelName.objects.get(country=country_name, level=level).name
                    form.base_fields[f'border{level}'].label = level_name
                    form.base_fields[f'border{level}'].queryset = Border.objects.filter(country=country_name,
                                                                                        level=level)
        return form

    def get_export_resource_class(self):
        return resources.CustomerExportResource

    def get_import_resource_class(self):
        return resources.CustomerImportResource

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'model_name': 'Customer'})
        return context




class CustomerQuestionChoiceInline(TimestampedBaseAdminMixin, admin.TabularInline):
    model = models.CustomerQuestionChoice
    extra = 0
    fields = ('text',)


@admin.register(models.CustomerQuestion)
class CustomerQuestionAdmin(TimestampedBaseAdmin):
    inlines = [
        CustomerQuestionChoiceInline,
    ]
    fields = ('text',)
