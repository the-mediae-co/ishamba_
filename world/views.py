import re

from django.contrib.gis.geos import Point
from django.http import JsonResponse
from django.views.generic import View

from world.models import Border, BorderLevelName
from world.utils import get_border_for_location, process_border_ajax_menus


class BordersForLocationView(View):

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        """
        Responds in JSON with the pk for the county that the given coordinate
        is within.

        If the coordinate is not within a county, we find the closest up to a
        threshold defined by `settings.WORLD_COUNTY_DISTANCE_CUTOFF`.

        Return:
            For success: 200, {"county": 20}
            For no match: 404, {"error": "No county found"}
            For bad args: 400, {"error": "Invalid location provided"}
        """
        lat_str = request.GET.get('lat')
        lon_str = request.GET.get('lng')

        try:
            point = Point(float(lon_str), float(lat_str), srid=4326)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid location provided."}, status=400)

        border0 = get_border_for_location(point, 0)
        if not border0:
            return JsonResponse({"error": "No border0 found"}, status=404)

        border1 = get_border_for_location(point, 1)
        if not border1:
            return JsonResponse({"error": "No border1 found"}, status=404)

        border2 = get_border_for_location(point, 2)
        if not border2:
            return JsonResponse({"error": "No border2 found"}, status=404)

        border3 = get_border_for_location(point, 3)
        if not border3:
            return JsonResponse({"error": "No border3 found"}, status=404)

        response = {
            'border0': border0.pk,
            'border1': border1.pk,
            'border2': border2.pk,
            'border3': border3.pk,
        }

        req_dict = self.request.GET.dict()
        req_dict.update({
            'changed_field': 'border1',
        })

        # Get the menu options, based on the location given
        response = process_border_ajax_menus(border0, border1, border2, border3, req_dict, response)
        # Populate the fields necessary to draw this location on the leaflet map
        if response['selected_border3s']:
            b3_id = response['selected_border3s'][0]
            b3 = Border.objects.get(id=b3_id)
            response.update({'border3_name': b3.name})
            response.update({'border3_label': response['border3_label']})
            response.update({'border3_geom': b3.border.json})
            response.update({'border3_centroid': b3.border.centroid.json})
        if response['selected_border2s']:
            b2_id = response['selected_border2s'][0]
            b2 = Border.objects.get(id=b2_id)
            response.update({'border2_name': b2.name})
            response.update({'border2_label': response['border2_label']})
            response.update({'border2_geom': b2.border.json})
            response.update({'border2_centroid': b2.border.centroid.json})

        return JsonResponse(response)


class BordersSearch(View):

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        """
        Responds in JSON with the names, bounding boxes and centroids of
        the borders that match the query.
        """
        query = request.GET.get('query')
        resp_data = []
        if query is not None:
            # Check if a lat,lng value was entered
            latlng_re = re.compile('(^[-+]?(?:[1-8]?\d(?:\.\d+)?|90(?:\.0+)?)),\s*([-+]?(?:180(?:\.0+)?|(?:(?:1[0-7]\d)|(?:[1-9]?\d))(?:\.\d+)?))$')
            latlng = latlng_re.findall(query)
            if latlng:
                a = float(latlng[0][0])
                b = float(latlng[0][1])
                # We assume the lat,lng coords are in East Africa, so allow them to be entered in either order
                lat = a if a < b else b
                lng = a if a > b else b
                resp_data.append({
                    'name': f'GPS: {lat}, {lng}',
                    'bbox': (lng - 0.05, lat - 0.05, lng + 0.05, lat + 0.05),
                    'center': {'lat': lat, 'lng': lng},
                    'border': Point(lng, lat, srid=4326).json,
                })
            else:
                # Not lat,lng coords so search for a name match
                matches = Border.objects.filter(name__icontains=query).order_by('country', 'name', 'parent__name')
                for match in matches:
                    level_name = BorderLevelName.objects.get(country=match.country, level=match.level).name
                    resp_data.append({
                        'name': f'{match.name}, {match.country} ({level_name})',
                        'bbox': match.border.extent,
                        'center': {'lat': match.border.centroid.y, 'lng': match.border.centroid.x},
                        'border': match.border.json,
                    })

        return JsonResponse({'matches': resp_data})
