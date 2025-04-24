QUERY_STRING = 'query string'
JSON = 'json'

SERVICES = {
    'auth': {
        'url': "https://data.awhere.com/api/weather/Login",
        'method': "POST",
    },
    'forecast': {
        'url': "https://data.awhere.com/api/weather",
        'method': "GET",
        'parameter_format': QUERY_STRING
    },
    'season': {
        'url': "https://data.awhere.com/api/weather/season",
        'method': "GET",
        'parameter_format': JSON,
    }
}

# the number of forecast days that aWhere provides is 8, but 6 days ahead gets
# us 7 days of forecasts
FORECAST_DAYS = 6

GDD_METHOD_STANDARD = 'standard'
GDD_METHOD_MIN_TEMP = 'min-temp'
GDD_METHOD_MIN_CAP = 'min-cap'

FORECAST_ATTRIBUTES = [
    # 'minTemperature',  # (lowest air temperature recorded during day, in degrees C)
    # 'maxTemperature',  # (highest air temperature recorded during day, in degrees C)
    # 'precip',  # (total daily precipitation, in mm)
    # 'accPrecip',  # (total accumulated precip from startDate in the requested period, in mm)
    # 'solar',  # (summation of total solar energy received during day, watt hours/sq. meter [wh/m2])
    # 'minHumidity',  # (lowest % relative humidity recorded for day, %)
    # 'maxHumidity',  # (highest % relative humidity recorded for day, %)
    # 'mornWind',  # (morning's highest wind speed in meters/second [m/s])
    # 'maxWind',  # (day's highest wind speed in meters/second [m/s])
    # 'gdd',  # (Growing Degree Days, # of heat units achieved per day, based upon 'base' and 'cap' Temp values)
    # 'accGdd',  # (total accumulated GDDs from startDate in the requested period, in heat units)
    'conditions',  # (including this attribute indicates that you are requesting that forecast co

]

OPTIONAL_INPUTS = {
    # optional values if you pass the 'conditions value'

    'conditionsType': 'basic',  # conditionsType - options are either 'basic'
    # or 'standard'. This specifies one of two available, pre-configured sets
    # of class-breaks we have for the conditions attributes. See "Forecast
    # Conditions Code Definitions" section near the end of this document for an
    # explanation of basic vs standard conditionsType.
    'intervals': '1',  # - options are either '1' or '4'. If '1', the returned
    # forecast conditions will be summarized per a 24-hour period. If '4', the
    # returned forecast conditions will be reported per the four daily 6-hour
    # intervals: early morning (midnight-0600), morning (0600-1200), afternoon
    # (1200-1800), and evening (1800-2400).
    'utcOffset': '3:00:00'  # - specifies the number of hours of offset
    # between specified lat/long location, and UTC time (e.g. "-5:00:00", or
    # "1:00:00")
}

CONDITIONS_ATTRIBUTES = [
    'minTemperature',  # (lowest air temperature forecast per the requested interval(s), in degrees C)
    'maxTemperature',  # (highest air temperature forecast per the requested interval(s), in degrees C)
    'precip',  # (total precipitation forecast during each requested interval(s), in mm)
    'solar',  # (total solar energy forecast per the requested interval(s), watt hours/sq. meter [wh/m2])
    'meanRelativeHumidity',  # (average % relative humidity forecast per the requested interval(s), %)
    'wind',  # (average wind speed forecast per the requested interval(s), in meters/second [m/s])
    'precipPercent',  # (% chance of precipitation forecast per the requested interval(s))
    'sunPercent',  # (% chance of sunshine forecast per the requested interval(s))
    'cloudPercent',  # (% chance of clouds forecast per the requested interval(s))
]
