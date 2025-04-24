

from taggit.utils import _edit_string_for_tags, _parse_tags


def tags_from_string(tag_string):
    """ Custom tag parser that creates multiple tags from individual forward
    slash delimited tags. Commas are still the major delimiter and are handled
    by the default taggit parser (`taggit.utils._parse_tags`).

    >>> tags_from_string('SSU/S01/E01,leaflet')
    [u'SSU', u'SSU/S01', u'SSU/S01/E01', u'leaflet']
    """
    return expand_tags(_parse_tags(tag_string))


def expand_tags(tags):
    """ Custom tag parser that creates multiple tags from individual forward
    slash delimited tags.

    >>> expand_tags(['SSU/S01/E01', 'leaflet'])
    [u'SSU', u'SSU/S01', u'SSU/S01/E01', u'leaflet']
    """
    # set to ensure we don't add duplicate tags
    final_tags = set()

    for tag in tags:
        parts = tag.split('/')

        for i in range(len(parts)):
            final_tags.add('/'.join(parts[0:i + 1]))

    return list(final_tags)


def collapse_tags(tags):
    """ Filters tags to exclude any tag whose name is a substring of another
    tag's name. These will be derived by `tags_from_string`.
    >>> string_from_tags([Tag.objects.create(name='SSU/S01'),
                          Tag.objects.create('SSU')])
    [<Tag: SSU/S01>]
    """

    return filter(lambda t: not any(t.name in x.name for x in tags if x != t),
                  tags)


def string_from_tags(tags):
    """ Custom `TAGGIT_STRING_FROM_TAGS` implementation that removes "sub-tags"
    i.e. tags that are sub-strings of other tags.

    Args:
        tags (Iterable): Iterable of Tag objects from which we derive the
            string representation.

    >>> string_from_tags([Tag.objects.create(name='SSU/S01'),
                          Tag.objects.create('SSU')])
    u'SSU/S01'
    """
    return _edit_string_for_tags(collapse_tags(tags))
