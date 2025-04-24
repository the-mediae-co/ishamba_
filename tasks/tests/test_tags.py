from taggit.models import Tag

from core.test.cases import TestCase

from tasks.tags import string_from_tags, tags_from_string


class CustomTagParsingTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.ssu = Tag.objects.create(name='SSU')
        self.ssu_s01 = Tag.objects.create(name='SSU/S01')
        self.ssu_s01_e01 = Tag.objects.create(name='SSU/S01/E01')
        self.leaflet = Tag.objects.create(name='leaflet')

    def test_tags_from_string_basic(self):
        tags = tags_from_string('SSU/S01/E01')
        self.assertSetEqual(set(tags),
                            set(['SSU', 'SSU/S01', 'SSU/S01/E01']))

    def test_tags_from_string_multiple_tags(self):
        tags = tags_from_string('SSU/S01/E01, leaflet')
        self.assertSetEqual(set(tags),
                            set(['SSU', 'SSU/S01', 'SSU/S01/E01',
                                 'leaflet']))

    def test_tags_from_string_quoted(self):
        tags = tags_from_string('"SSU/S01/E01"')
        self.assertSetEqual(set(tags),
                            set(['SSU', 'SSU/S01', 'SSU/S01/E01']))

    def test_string_from_tags(self):
        tags = [self.ssu, self.ssu_s01, self.ssu_s01_e01]
        self.assertEqual(string_from_tags(tags), 'SSU/S01/E01')

    def test_string_from_tags_multiple(self):
        tags = [self.ssu, self.ssu_s01, self.ssu_s01_e01, self.leaflet]
        self.assertEqual(string_from_tags(tags), 'SSU/S01/E01, leaflet')
