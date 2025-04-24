from typing import Any

from django.db import models
from django.core.exceptions import ImproperlyConfigured

from search.constants import ANALYZERS


class ESAnalyzedCharField(models.CharField):
    analyzer: str
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.analyzer = kwargs.pop('analyzer', None)
        if self.analyzer not in ANALYZERS:
            raise ImproperlyConfigured(f"Analyzer must be one of {','.join(ANALYZERS)}")
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["analyzer"] = self.analyzer
        return name, path, args, kwargs


class ESAnalyzedTextField(models.TextField):
    analyzer: str
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.analyzer = kwargs.pop('analyzer', None)
        if self.analyzer not in ANALYZERS:
            raise ImproperlyConfigured(f"Analyzer must be one of {','.join(ANALYZERS)}")
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["analyzer"] = self.analyzer
        return name, path, args, kwargs
