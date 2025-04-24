from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django_tables2 import SingleTableView

from exports.models import Export, MapExport
from taggit.utils import _parse_tags

from customers.models import Customer
from sms.models import IncomingSMS

from .filters import CustomerExportFilter, IncomingSMSExportFilter
from .forms import CustomerFieldSelectionForm, IncomingSMSFieldSelectionForm
from .tables import ExportTable
from .tasks import generate_export, generate_map


class BaseExportCreateView(TemplateView):
    """ Base view for creating exports.
    """

    http_method_names = ['get', 'post']

    filter_form = None
    field_selection_form = None
    model = None
    export_model = Export
    export_task = generate_export

    def get_filter_form_kwargs(self):
        kwargs = {
            'queryset': self.model.objects.all()
        }
        if self.request.method.lower() == "post":
            kwargs['data'] = self.request.POST

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            **kwargs)

        context['filter'] = self.filter

        context['field_selection_form'] = self.field_selection_form(
            initial={'fields': self.DEFAULT_EXPORTED_FIELDS}
        )

        return context

    def dispatch(self, request, *args, **kwargs):
        self.filter = self.filter_form(**self.get_filter_form_kwargs())
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        if self.filter.is_bound and self.filter.form.is_valid():
            self.create_export(
                self.process_filter_data(self.filter.form.cleaned_data))
            return HttpResponseRedirect(self.success_url)
        else:
            return self.render_to_response(context)

    def process_filter_data(self, cleaned_data):
        """ Due to implementation specifics tag filters need to be
        pre-processed before using them as filters.
        """
        processed = {}

        for field_name, value in cleaned_data.items():
            if 'tag' in field_name:
                value = _parse_tags(value)
            processed[field_name] = value

        return processed

    def create_export(self, filters):
        """ Creates a new Export instance using filters specified via the
        filter form and starts the `generate_export` Celery task.
        """
        # any key that is in complete_record_filters will be included in the
        # filter even if it equates to false (like an empty string)
        complete_record_filters = getattr(self.filter.form,
                                          'complete_record_filters', {})

        export_filters = {}
        for key, val in filters.items():
            if val or (key in complete_record_filters):
                export_filters[key] = val

        export = self.export_model.objects.create(
            content_type=ContentType.objects.get_for_model(self.model),
            filters=export_filters,
            fields={'fields': list(self.get_exported_fields())},
            created_by=self.request.user
        )
        self.export_task.delay(export.pk, self.request.tenant.schema_name)

    def get_exported_fields(self):
        field_selection_form = self.field_selection_form(self.request.POST)
        if field_selection_form.is_valid():
            return field_selection_form.cleaned_data['fields']

        return self.DEFAULT_EXPORTED_FIELDS


class ExportView(SingleTableView):
    model = Export
    table_class = ExportTable
    template_name = 'exports/export_list.html'


class CustomerExportCreateView(BaseExportCreateView):
    """ Handles the generation of Customer exports. Currently the exported
    fields are hard-coded, however, this is to change in the future.
    """
    # TODO: FIX ME (support multiple phones)
    filter_form = CustomerExportFilter
    field_selection_form = CustomerFieldSelectionForm
    model = Customer
    DEFAULT_EXPORTED_FIELDS = ('name', 'sex', 'dob', 'phones__number',
                               'county__name', 'postal_address', 'postal_code')

    template_name = 'exports/customer_export.html'
    success_url = reverse_lazy('exports:list')


class IncomingSMSExportCreateView(BaseExportCreateView):
    filter_form = IncomingSMSExportFilter
    field_selection_form = IncomingSMSFieldSelectionForm
    model = IncomingSMS
    DEFAULT_EXPORTED_FIELDS = ('task__id', 'at', 'sender', 'text')

    template_name = 'exports/incomingsms_export.html'
    success_url = reverse_lazy('exports:list')


class MapExportView(SingleTableView):
    model = MapExport
    table_class = ExportTable
    template_name = 'exports/map_list.html'


class MapExportCreateView(BaseExportCreateView):
    # TODO: FIX ME (support multiple phones)
    filter_form = CustomerExportFilter
    field_selection_form = CustomerFieldSelectionForm
    model = Customer
    export_model = MapExport
    export_task = generate_map
    DEFAULT_EXPORTED_FIELDS = ('name', 'county__name', 'village', 'ward')

    template_name = 'exports/maps_export.html'
    success_url = reverse_lazy('exports:maps_list')
