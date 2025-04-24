import json
from typing import Any, Union

from django.template import Library
from django.utils.html import format_html
from django.utils.safestring import mark_safe


register = Library()


@register.filter
def split(value: str, sep: str) -> Union[str, list[str]]:
    if not value:
        return value

    return value.split(sep)


@register.filter
def as_json(value: Any) -> str:
    return mark_safe(json.dumps(value, sort_keys=True))


@register.filter
def json_script(value: Any, element_id: str) -> str:
    """
    Escape all the HTML/XML special characters with their unicode escapes, so
    value is safe to be output anywhere except for inside a tag attribute. Wrap
    the escaped JSON in a script tag.

    Like the built-in, but uses our own encoder
    """
    json_str = json.dumps(value, cls=JSONEncoder).translate(_json_script_escapes)
    return format_html(
        '<script id="{}" type="application/json">{}</script>',
        element_id, mark_safe(json_str)
    )
