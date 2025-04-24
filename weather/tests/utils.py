import datetime

from django.contrib.gis.geos import Point


def get_base_forecast_data(latitude, longitude, date, conditions=None, **kwargs):
    fc_data = {
        'provider': 'aWhere',
        'conditions': [{
            'meanRelativeHumidity': 86,
            'maxTemperature': 17,
            'cloudPercent': 83,
            'sunPercent': 16,
            'minTemperature': 7,
            'precipPercent': 70,
            'precip': 37,
            'condText': 'Partly Cloudy, Light Rain, Light Wind/Calm',
            'solar': 4962,
            'wind': 0.87,
            'condCode': '221'}]
    }
    fc_data['longitude'] = longitude,
    fc_data['latitude'] = latitude,
    start_time = datetime.datetime.combine(date, datetime.time()).isoformat()
    fc_data['date'] = start_time

    fc_data['conditions'][0]['startTime'] = start_time
    fc_data['conditions'][0]['endTime'] = datetime.datetime.combine(
        date,
        datetime.time(23, 59, 59, 999)).isoformat()
    if conditions is not None:
        fc_data['conditions'][0].update(conditions)
    return fc_data


def get_point(location_dict):
    return Point(location_dict['lon'], location_dict['lat'])
