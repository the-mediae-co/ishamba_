from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils.functional import cached_property
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, MultiSearch

log = logging.getLogger('search')


from typing import Any


def get_es_mapping(field: models.Field) -> dict[str, str]:
    if field.many_to_one or field.one_to_one or field.many_to_many:
        return {'type': 'integer'}

    int_fields = (
        models.IntegerField, models.BigIntegerField,
        models.AutoField, models.PositiveIntegerField,
        models.PositiveBigIntegerField, models.PositiveSmallIntegerField
    )

    if isinstance(field, int_fields):
        return {'type': 'integer'}

    if isinstance(field, models.BooleanField):
        return {'type': 'boolean'}

    if isinstance(field, models.FloatField):
        return {'type': 'float'}

    if isinstance(field, models.DecimalField):
        return {'type': 'float'}

    if isinstance(field, models.DateTimeField):
        return {'type': 'date'}

    if analyzer := getattr(field, 'analyzer', None):
        return {'type': 'text', 'analyzer': analyzer}

    return {'type': 'keyword'}


class ESIndexableMixin(object):
    INDEX_FIELDS: list[str] = []
    STRICT: bool = True
    NESTED: bool = False
    INDEX_ON_SAVE = True
    UNINDEX_ON_DELETE = True

    @classmethod
    @property
    def name(cls) -> str:
        return cls.__name__.lower()

    @classmethod
    @property
    def index(cls) -> str:
        app_label = cls._meta.app_label.lower()
        return f"{settings.INDEX_PREFIX}_{app_label}_{cls.__name__.lower()}"

    @property
    def es_id(self) -> str:
        if not self.pk:
            return ""
        return f"{self.content_type}.{self.pk}"

    @classmethod
    def mapping(cls, **kwargs: Any) -> dict[str, Any]:
        mapping: dict[str, Any] = {}

        # Process fields
        for field in cls._meta.get_fields():
            if field.name not in cls.INDEX_FIELDS:
                continue

            field_mapping = get_es_mapping(field)

            if field.many_to_one or field.one_to_one or field.many_to_many:
                mapping[f'{field.name}_id'] = field_mapping

            if related_model := getattr(field, 'related_model'):
                if hasattr(related_model, 'mapping') and related_model.NESTED:
                    nested_mapping = field.remote_field.model.mapping()
                    mapping[field.name] = {"type": "nested", **nested_mapping}
            else:
                mapping[field.name] = field_mapping

        full_mapping = {"properties": mapping}

        if not cls.NESTED:
            full_mapping["dynamic"] = "strict"

        return full_mapping

    def to_dict(self, **kwargs) -> dict[str, Any]:
        data = {}
        for field_name in self.INDEX_FIELDS:
            try:
                field = self._meta.get_field(field_name)
            except FieldDoesNotExist:
                value = getattr(self, field.name, None)
                if value is not None:
                    data[field.name] = value
            else:
                if field.many_to_one or field.one_to_one:
                    value = getattr(self, f'{field.name}_id', None)
                    if value is not None:
                        data[f'{field.name}_id'] = value

                if related_model := getattr(field, 'related_model'):
                    if issubclass(related_model, ESIndexableMixin) and related_model.NESTED:
                        related_instance = getattr(self, field.name, None)
                        if related_instance is not None:
                            data[field.name] = related_instance.to_dict()
                else:
                    value = getattr(self, field.name, None)
                    if value is not None:
                        data[field.name] = value
        return data

    def should_index(self) -> bool:
        """
        This method must be implemented in child classes to determine
        whether `self.obj` belongs in the index.
        """
        raise NotImplementedError()

    def should_keep(self) -> bool:
        """
        This method can be implemented in child classes to prevent
        `self.obj` from being removed from the index.
        """
        return False

    @cached_property
    def content_type(self) -> str:
        """
        Caches the `ContentType` lookup for self.model
        """
        from django.contrib.contenttypes.models import ContentType
        return '.'.join(ContentType.objects.get_for_model(self).natural_key())

    @classmethod
    @property
    def search(cls) -> Search:
        """
        A new instance of an `elastcserch_dsl.Search` object
        """

        search = Search(index=cls.index, using=cls.es)
        search = search.params(request_timeout=cls.timeout)
        return search

    @property
    def msearch(self) -> MultiSearch:
        """
        A new instance of an `elastcserch_dsl.MultiSearch` object
        """
        return MultiSearch(index=self.index, using=self.es)

    @classmethod
    @property
    def timeout(self) -> int:
        return settings.ELASTICSEARCH['default']['timeout']

    @classmethod
    @property
    def es(cls) -> Elasticsearch:
        """
        A wrapped Elastcisearch client, that automatically
        applies index kwargs to its methods
        """
        return Elasticsearch(hosts=settings.ELASTICSEARCH['default']['host'], timeout=cls.timeout)

    @classmethod
    def log(cls, message: str, obj: Any) -> None:
        """
        Log helper for indexing actions. Adds the source stack
        of the indexing call from within the app. Only active
        if settings.DEBUG=True. To enable logging, add the following
        to your local_settings:
        """
        if not settings.DEBUG:
            return
        log.debug(message)

    @classmethod
    def index_one(cls, obj: ESIndexableMixin) -> dict[str, Any]:
        """
        Extract a document from and index/delete (depending on
        `should_index()`) a single object.
        """
        if obj.should_index():
            body: dict[str, Any] = obj.to_dict()
            try:
                cls.es.index(document=body, id=obj.es_id, index=obj.index)
                return body

            except Exception as e:
                log.error('Failure in es write: %s', e)
        elif not obj.should_keep():
            try:
                cls.es.delete(id=obj.es_id, ignore=404)

            except Exception as e:
                log.error('Failure in es write: %s', e)

    @classmethod
    def index_many(cls, objs: list[ESIndexableMixin]) -> None:
        """
        Extract a document from and index/delete (depending on
        `should_index()`) a single object.
        """
        for obj in objs:
            cls.index_one(obj)

    @classmethod
    def delete_one(cls, obj: ESIndexableMixin) -> None:
        """
        Delete a document from the index.
        """
        cls.log('Delete One', obj)
        try:
            cls.es.delete(id=obj.es_id, index=cls.index, ignore=404)
        except Exception as e:
            log.error('Failure in es write: %s', e)

    @classmethod
    def from_index(cls, id: int) -> dict:
        """
        Fetch a document from the index.
        """

        from django.contrib.contenttypes.models import ContentType
        content_type = '.'.join(ContentType.objects.get_for_model(cls).natural_key())
        return cls.es.get(id=f"{content_type}.{id}", index=cls.index)['_source']

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        if self.INDEX_ON_SAVE:
            self.index_one(self)

    def delete(self, *args, **kwargs) -> None:
        es_id = self.es_id
        index = self.index
        super().delete(*args, **kwargs)
        if self.UNINDEX_ON_DELETE:
            try:
                self.es.delete(id=es_id, index=index, ignore=404)
            except Exception as e:
                log.error('Failure in es delete: %s', e)
