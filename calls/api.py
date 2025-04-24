import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils.timezone import localtime, now
from django.http import JsonResponse

from rest_framework import permissions
from rest_framework.generics import (ListAPIView, RetrieveAPIView,
                                     RetrieveUpdateAPIView)

from core.utils.functional import is_jquery_ajax
from customers.models import Customer
from markets.models import MarketPrice
from sms.models import IncomingSMS, SMSRecipient, OutgoingSMS
from weather.models import ForecastDay
from world.models import Border, BorderLevelName
from world.utils import process_border_ajax_menus, is_valid_border_for_location

from .models import Call
from .serializers import (CallSerializer, CCOCallSerializer,
                          ForecastDaySerializer, IncomingSMSSerializer,
                          OutgoingSMSSerializer, MarketPriceSerializer)

from logging import getLogger
logger = getLogger(__name__)

User = get_user_model()


class CallDetailView(RetrieveUpdateAPIView):
    """
    Called CallDetailView, but actually only implements GET, PUT and PATCH.
    We have expanded the view to also enable retrieving and updating details
    for the customer associated with this call.
    """
    model = Call
    serializer_class = CallSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = Call.objects.all()

    def get(self, request, *args, **kwargs):
        # First serialize the CallDetailView
        response = super().retrieve(request, *args, **kwargs)
        # Then add the location and gender details for the customer's updates_form ajax menu
        try:
            customer_dict = response.data.get('customer')
            customer_id = customer_dict['id']
            customer = Customer.objects.get(pk=customer_id)
        except (KeyError, Customer.objects.DoesNotExist) as e:
            return response

        selected_border0s = [customer.border0_id] or []
        selected_border1s = [customer.border1_id] or []
        selected_border2s = [customer.border2_id] or []
        selected_border3s = [customer.border3_id] or []

        process_border_ajax_menus(selected_border0s, selected_border1s,
                                  selected_border2s, selected_border3s,
                                  request.data, response.data)

        response.data.update({
            'gender': customer.sex,
        })

        # Update the response data used by the leaflet map
        # Note that the response data for border2_label and border3_label
        # should be set above in process_border_ajax_menus
        if customer.location:
            response.data.update({'customerGPS': dict(zip(('lng', 'lat'), customer.location.coords))})
        else:
            response.data.update({'customerGPS': None})

        if customer.border3:
            # Add the geometry (multipolygon) of the border3 for drawing on a leaflet map
            b2 = customer.border2
            response.data.update({
                'border2_name': b2.name,
                'border2_geom': b2.border.json,
                'border2_centroid': b2.border.centroid.json,
            })
            b3 = customer.border3
            response.data.update({
                'border3_name': b3.name,
                'border3_geom': b3.border.json,
                'border3_centroid': b3.border.centroid.json,
            })
        else:
            response.data.update({
                'border2_name': None,
                'border2_geom': None,
                'border2_centroid': None,
            })
            b3 = customer.border3
            response.data.update({
                'border3_name': None,
                'border3_geom': None,
                'border3_centroid': None,
            })
        response.data.update({'enableLeafletEditing': True})

        return response

    def partial_update(self, request, *args, **kwargs):
        # This method normally performs partial updates to the Call object, but not
        # the customer. We add logic here, recognizing an ajax request and adding
        # the ability to handle customer updates.

        # Note that the AngularJS queries to partial_update() do not have
        # jquery headers so this test returns False.
        if not is_jquery_ajax(request):
            # If not jquery ajax, it's an AngularJS request
            return super().partial_update(request, *args, **kwargs)
        else:
            # PATCH data comes in via the POST attribute in the request
            if hasattr(request, 'POST'):
                pk = kwargs.get('pk')
                try:
                    call = self.queryset.get(pk=pk)
                except Call.DoesNotExist:
                    # This should never happen. But if it does, just send back an empty response
                    logger.error(f"CallDetailView.partial_update: Call record not found.")
                    return JsonResponse({})

                customer = call.customer
                if not customer:
                    logger.error(f"CallDetailView.partial_update: Call record has no customer.")
                    return JsonResponse({})

                # Technically only one field should change at a time, with each
                # change triggering an ajax post. However, given network latencies,
                # some may get cancelled or overwritten. We should therefore
                # save all of the presented data.
                lat = request.POST.get('lat')
                lng = request.POST.get('lng')
                if lat and lng:
                    customer.location = Point(x=float(lng), y=float(lat), srid=4326)
                customer.border0_id = request.POST.get('border0')
                customer.border1_id = request.POST.get('border1')
                customer.border2_id = request.POST.get('border2')
                border3_id = request.POST.get('border3')
                if not lat and not lng and border3_id:
                    # Update the gps location to the centroid of their border3
                    border3 = Border.objects.get(id=border3_id)
                    if customer.location is None or not border3.border.contains(customer.location):
                        customer.location = border3.border.centroid
                # Regardless, set the customer's border3 value
                customer.border3_id = border3_id
                # If a border is set to None, clear the finer grained borders
                if customer.border1_id is None:
                    customer.border2_id = customer.border3_id = customer.location = None
                elif customer.border2_id is None:
                    customer.border3_id = customer.location = None
                elif customer.border3_id is None:
                    customer.location = None

                customer.sex = request.POST.get('gender', '')  # null is not a valid value for this field
                customer.save(update_fields=['border0_id', 'border1_id', 'border2_id', 'border3_id', 'location', 'sex'])

                # Regardless of the field that changed, process the ajax location menu settings first
                selected_border0s = request.POST.get('border0', [])
                selected_border1s = request.POST.get('border1', [])
                selected_border2s = request.POST.get('border2', [])
                selected_border3s = request.POST.get('border3', [])
                response = process_border_ajax_menus(selected_border0s, selected_border1s,
                                                     selected_border2s, selected_border3s, request.POST.dict())

                if customer.border0:
                    # Set the border level names, even if we don't know the customer's other location details
                    b2_label = BorderLevelName.objects.get(country=customer.border0, level=2).name
                    b3_label = BorderLevelName.objects.get(country=customer.border0, level=3).name
                else:
                    # Default to Kenya
                    b2_label = 'Subcounty'
                    b3_label = 'Ward'
                response.update({
                    'border2_label': b2_label,
                    'border3_label': b3_label,
                })

                if customer.location:
                    gps_string = dict(zip(('lng', 'lat'), customer.location.coords))
                    response.update({'customerGPS': json.dumps(gps_string)})
                elif customer.border3:
                    gps_string = dict(zip(('lng', 'lat'), customer.border3.border.centroid))
                    response.update({'customerGPS': json.dumps(gps_string)})
                else:
                    response.update({'customerGPS': None})

                if customer.border3:
                    # Add the geometry (multipolygon) of the border3 for drawing on a leaflet map
                    b2 = customer.border2
                    response.update({
                        'border2_name': b2.name,
                        'border2_label': b2_label,
                        'border2_geom': b2.border.json,
                        'border2_centroid': b2.border.centroid.json,
                    })
                    b3 = customer.border3
                    response.update({
                        'border3_name': b3.name,
                        'border3_label': b3_label,
                        'border3_geom': b3.border.json,
                        'border3_centroid': b3.border.centroid.json,
                    })
                else:
                    response.update({
                        'border2_name': None,
                        'border2_label': b2_label,
                        'border2_geom': None,
                        'border2_centroid': None,
                    })
                    response.update({
                        'border3_name': None,
                        'border3_label': b3_label,
                        'border3_geom': None,
                        'border3_centroid': None,
                    })

                if request.POST.get('changed_field') == 'gender':
                    gender = request.POST.get('gender', '')
                    # If the changed field was gender, add it to the response
                    response.update({'gender': gender})
            else:
                response = {}

            return JsonResponse(response)


class CCOView(RetrieveAPIView):
    """
    Given a CCO (-id-) username, returns mainly just the single call connected
    to that CCO.
    """
    model = User
    serializer_class = CCOCallSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'username'

    queryset = User.objects.all()


class ForecastDayListView(ListAPIView):
    """ Given a weather area id, returns forecasts. """
    model = ForecastDay
    serializer_class = ForecastDaySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'weather_area'

    def get_queryset(self):
        pk = self.kwargs['pk']
        today = localtime(now()).date()
        return ForecastDay.objects.filter(area=pk, target_date__gte=today)


class MarketPriceListView(ListAPIView):
    """ Given a commodity id, returns latest prices per market. """
    model = MarketPrice
    serializer_class = MarketPriceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        pk = self.kwargs['pk']
        return (MarketPrice.objects.filter(commodity__id=pk)
                                   .order_by('market_id', '-date')
                                   .distinct('market'))


class OutgoingSMSListView(ListAPIView):
    """ Given a customer id, returns their outgoing sms messages. """
    model = OutgoingSMS
    serializer_class = OutgoingSMSSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        pk = self.kwargs['pk']
        ids = SMSRecipient.objects.filter(recipient__id=pk).order_by('-created').values_list('message_id', flat=True)
        messages = OutgoingSMS.objects.filter(id__in=ids[:50]).order_by('-time_sent')
        return (messages)


class IncomingSMSListView(ListAPIView):
    """ Given a customer id, returns their incoming sms messages. """
    model = IncomingSMS
    serializer_class = IncomingSMSSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        pk = self.kwargs['pk']
        return (IncomingSMS.objects.filter(customer__id=pk)
                                   .order_by('-created')[:50])
