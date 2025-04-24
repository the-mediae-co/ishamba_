import django_tables2 as tables
from exports.models import Export


class ExportTable(tables.Table):
    """ Table for rendering all `Export`s
    """
    created_by = tables.TemplateColumn(template_name='exports/user_chip.html')
    download = tables.TemplateColumn(template_name='exports/download_btn.html',
                                     orderable=False)

    class Meta:
        model = Export
        order_by = ('-created_at', )
        attrs = {"class": "striped"}
        exclude = ('id', 'fields', 'exported_file', 'filters')
        empty_text = "No exports"
        template_name = "tables/tables.html"
