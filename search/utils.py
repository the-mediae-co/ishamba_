from __future__ import annotations

import datetime
import gc
import itertools
import json
import logging
import os
from math import ceil
from multiprocessing import Pool
from typing import Any, Generator, Optional, Tuple

from elasticsearch.exceptions import RequestError

from django import db
from django.core.paginator import Paginator
from django.db import models
from django.db.models.query import QuerySet
from search.indexes import ESIndexableMixin


log = logging.getLogger('bso')


def chunked(iterable: list, size: int = 100,collect: bool = True) -> Generator[Tuple[models.Model, ...], None, None]:
    """
    Iterate through iterable by chunks of `size`. If `collect` is True,
    run the garbage collector after every chunk
    """
    if isinstance(iterable, QuerySet) and hasattr(iterable, 'iterator'):
        iterable = iterable.iterator()

    iterator = iter(iterable)

    chunk = tuple(itertools.islice(iterator, size))
    while chunk:
        yield chunk

        if collect:
            gc.collect()

        chunk = tuple(itertools.islice(iterator, size))


def create_index(indexable: type[ESIndexableMixin]) -> Optional[bool]:
    """
    Create an index for an instance of `Index` class
    """
    created = False
    es = indexable.es
    index = indexable.index
    if not es.indices.exists(index):
        es.indices.create(body={"mappings": indexable.mapping()}, index=index)
        log.info('Created index: %s via %s', index, es)
        created |= True
    else:
        log.info('Index exists: %s via %s', index, index)
        created |= False
    return created


def diff_mapping(indexable: type[ESIndexableMixin], old_to_new: bool = True) -> Optional[dict[str, Any]]:
    """
    Returns a dict with differences between an index's mapping
    on the server and the defined local mapping. If old_to_new is
    True (default), this will return fields defined in the local
    mapping that will conflict with what is on the server. If it
    is False, it will return fields present in the mapping on the
    server, but not in the locally defined mapping.
    """
    index = indexable.index
    es = indexable.es
    old = es.indices.get_mapping(index=index)[index]['mappings']['properties']
    new = indexable.mapping()['properties']

    def _diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        d = {}

        for key, value in new.items():

            # A whole key was added in new..
            if key not in old:

                # SKIP if it's a type: obj/nested, as those aren't returned by the server
                if key == 'type' and value in ['object', 'nested']:
                    continue

                # ADD to the diff otherwise
                else:
                    d[key] = value

            # This shouldn't happen in practice but if they pytthon types of two values differ
            # it should considered a difference and ADDed. This also ensures that the dict key
            # accesses in the next elif step will work
            elif not isinstance(value, str) and not isinstance(value, type(old[key])):
                d[key] = value

            # The recursive bit, both new and old values are dicts
            elif isinstance(value, dict):
                # Get the diff of the values dicts...
                _d = _diff(old[key], value)

                # If they differ...
                if _d:

                    # index: analyzed is common in mapping definitions, but is not
                    # returned from the server. If this is the only difference, SKIP it
                    if len(_d) == 1 and 'index' in _d and _d['index'] == 'analyzed':
                        continue

                    # And we're dealing with a non-nested field definition, ADD the WHOLE
                    # field definition
                    if 'type' in value and 'properties' not in value:
                        d[key] = value

                    # Otherwise, ADD just the difference
                    else:
                        d[key] = _d

            # This is a straight up difference in something like a string, ADD it
            elif value != old[key]:
                d[key] = value

            # That's all the differences we're concerned with.
            # If we've got this far, SKIP this key
            else:
                continue

        return d
    if old_to_new:
        return _diff(old, new)
    else:
        return _diff(new, old)


def update_mapping(indexable: type[ESIndexableMixin]) -> None:
    """
    Attempt to update/put index's mapping on the server.
    This will fail if ES cannot merge the mappings
    """
    index = indexable.index
    es = indexable.es
    try:
        es.indices.put_mapping(body=indexable.mapping(), index=index)
        log.info('Updating mapping for: %s via %s', index, es)
    except RequestError:
        print('Mappings differ:\n\n{}'.format(
            json.dumps(diff_mapping(indexable), indent=2, sort_keys=True)))
        raise


def index_docs(indexable: type[models.Model], since: datetime.datetime = None, parallel: bool = False) -> None:
    """
    Index every document for an indexable,
    """
    if not issubclass(indexable, ESIndexableMixin):
        raise ValueError(f"{indexable} is not indexable")
    index = indexable.index
    qs = indexable.objects.all()
    total_count = qs.count()
    if not parallel:
        log.info('Indexing %d documents for %s.%s',total_count, index)
        indexable.index_many(qs)
    else:
        cpu_count = os.cpu_count()
        log.info(
            'Indexing %d documents in %d processes for %s.',
            total_count, cpu_count, index)
        paginator = Paginator(qs, ceil(total_count / cpu_count))
        pages = [paginator.get_page(i) for i in paginator.page_range]
        # Required to ensure that each process has its own DB connection
        db.connections.close_all()
        with Pool(cpu_count) as p:
            p.map(indexable.index_many, pages)


def delete_index(indexable: type[ESIndexableMixin]) -> Optional[bool]:
    """
    Deletes an index for instance of `Index` class
    """
    deleted = False
    es = indexable.es
    if es.indices.exists(indexable.index):
        es.indices.delete(indexable.index)
        log.info('Deleted index: %s via %s', indexable.index, es)
        deleted |= True
    else:
        deleted |= False
    return deleted


def clear_docs(indexable: type[ESIndexableMixin]) -> None:
    """
    Removes all the documents in an index
    """
    # There may be non-visible documents that could be missed
    # by delete_by_query unless this refresh occurs
    index = indexable.index
    es = indexable.es
    es.indices.refresh()

    res = es.delete_by_query(
        index=index,
        body={'query': {'match_all': {}}},
        _source=False,
        conflicts='proceed',
        refresh=True,
        scroll_size=100,
        wait_for_completion=True
    )
    log.info('Cleared index: %s, took: %s', index, res['took'])


def document_iterator(indexable: type[ESIndexableMixin]) -> Generator:
    """
    Use the scan/scroll API to efficiently iterate through all documents
    in an index in batches of 100. The 30m scroll is refreshed on each batch
    ie. you have 30 minutes to work on each batch.
    """
    for hit in indexable.search.scan():
        yield hit
