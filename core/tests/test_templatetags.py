from django.template import Context, Template

from core.test.cases import TestCase

from ..templatetags.message_tags import natural_join, values_for
from ..templatetags.oneliner_tag import collapse_whitespace, strip_lines


class NaturalJoinFilterTestCase(TestCase):

    def test_empty_list(self):
        self.assertEqual(natural_join([]), '')

    def test_single_item(self):
        self.assertEqual(natural_join(['Nakuru']), 'Nakuru')

    def test_two_items(self):
        self.assertEqual(natural_join(['Nakuru', 'Thika']), 'Nakuru and Thika')

    def test_many_items(self):
        items = [
            'Nakuru',
            'Thika',
            'Nairobi',
            'Kisumu',
            'Mombasa',
        ]
        expected = 'Nakuru, Thika, Nairobi, Kisumu and Mombasa'
        self.assertEqual(natural_join(items), expected)

    def test_not_a_list(self):
        val = None

        with self.assertRaises(TypeError):
            natural_join(val)


class ValuesForTestCase(TestCase):
    items = [
        {
            'first': 1,
            'second': 2,
        },
        {
            'first': 3,
            'second': 4,
        },
    ]

    def test_key_missing(self):
        self.assertEqual(values_for(self.items, 'missing'), ['', ''])

    def test_key_found(self):
        self.assertEqual(values_for(self.items, 'first'), [1, 3])

    def test_not_a_list(self):
        val = None

        with self.assertRaises(TypeError):
            values_for(val)


class OnelinerTestCase(TestCase):

    def render_template(self, string, ctx={}):
        return Template(string).render(Context(ctx))

    def test_strip_lines(self):
        val = "First line\n\nSecond line\n\nThird line"
        expected = "First lineSecond lineThird line"
        self.assertEqual(strip_lines(val), expected)

    def test_collapse_whitespace(self):
        val = "First   line\n\n\tSecond  line\nThird line"
        # Collapses newlines as well, which is why we strip them first
        expected = "First line Second line Third line"
        self.assertEqual(collapse_whitespace(val), expected)

    def test_render(self):
        expected = "Maize 100g: NAI 5000, MOM 2000. And then this other thing.\n"

        output = self.render_template(
            "{% load oneliner_tag %}"
            "{% oneliner %}\n\n"
            " \tMaize 100g: NAI 5000, MOM 2000.\n\n"
            " And then this other thing. \t\n\n"
            "{% endoneliner %}"
        )

        self.assertEqual(output, expected)
