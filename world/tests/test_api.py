import json
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from django_tenants.test.client import TenantClient as Client

from core.test.cases import TestCase

from ..models import Border


class CountyForLocationTests(TestCase):

    def setUp(self):

        self.api_url = reverse('borders_for_location')
        self.client = Client(self.tenant)
        self.nairobi = Border.objects.get(name='Nairobi', country='Kenya', level=1)
        self.user = User.objects.create_user('john', 'test@email.com', 'foo')

    def test_location_within_county(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(
            self.api_url,
            data={'lat': '-1.2729360401038594', 'lng': '36.863250732421875'},
            follow=True,
        )
        resp_json = resp.json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_json['border0'], self.nairobi.parent.pk)
        self.assertEqual(resp_json['border1'], self.nairobi.pk)

    def test_no_params(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(self.api_url, follow=True)
        self.assertEqual(resp.status_code, 400)

    def test_no_county_found(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(
            self.api_url,
            data={'lat': '36.863250732421875', 'lng': '-1.2729360401038594'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 404)

    def test_county_nearby(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(
            self.api_url,
            data={'lat': '-1.335176', 'lng': '36.963514'},
            follow=True,
        )
        # Confirm this point is not within the county
        point = Point(36.963514, -1.335176, srid=4326)
        self.assertFalse(self.nairobi.border.contains(point))
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.content, b'{"county": %d}' % self.nairobi.pk)

    def test_border_search_by_name(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(
            reverse('search'),
            data={'query': 'mig'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        response_data = json.loads(resp.content)
        self.assertTrue('matches' in response_data)
        self.assertEqual(4, len(response_data['matches']))

    def test_border_search_by_gps(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(
            reverse('search'),
            data={'query': '36.81011363782375, -1.2302235172902174'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        response_data = json.loads(resp.content)
        self.assertTrue('matches' in response_data)
        self.assertEqual(1, len(response_data['matches']))
        self.assertTrue(response_data['matches'][0]['name'].startswith('GPS'))
        self.assertEqual('Point', json.loads(response_data['matches'][0]['border'])['type'])

    def test_border_invalid_search(self):
        self.client.login(username='john', password='foo')
        resp = self.client.get(
            reverse('search'),
            data={'query': '36.810'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        response_data = json.loads(resp.content)
        self.assertTrue('matches' in response_data)
        self.assertEqual(0, len(response_data['matches']))
