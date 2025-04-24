var CallResource = ['$resource', function CallResourceFactory($resource) {
    return $resource('/calls/api/call/:id/', {
        id: '@id'
    },
    {
        'partial_update': { method:'PATCH' }
    });
}];

var CCOResource = ['$resource', function CCOResourceFactory($resource) {
    return $resource('/calls/api/cco/:username/', {
        username: '@username'
    });
}];

var ForecastDaysResource = ['$resource', function ForecastDaysResourceFactory($resource) {
    return $resource('/calls/api/weather_area/:id/forecast_days/', {
        id: '@id',
        refresh: '@refresh'
    });
}];

var MarketPricesResource = ['$resource', function MarketPricesResourceFactory($resource) {
    return $resource('/calls/api/commodity/:id/latest_prices/', {
        id: '@id',
    });
}];

var OutgoingSMSResource = ['$resource', function OutgoingSMSResourceFactory($resource) {
    return $resource('/calls/api/customer/:id/outgoing_sms/', {
        id: '@id',
    });
}];

var IncomingSMSResource = ['$resource', function IncomingSMSResourceFactory($resource) {
    return $resource('/calls/api/customer/:id/incoming_sms/', {
        id: '@id',
    });
}];
