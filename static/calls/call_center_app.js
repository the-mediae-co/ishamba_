
var app = angular.module('CallCenterApp', ['ngRoute', 'ngResource', 'timer']);

app.config(['$routeProvider',
    function($routeProvider) {
        $routeProvider.
            when('/call', {
                templateUrl: g_in_call_template,
                controller: 'InCallController'
            }).
            otherwise({
                templateUrl: g_call_queue_template,
                controller: 'CallQueueController'
            });
    }]);

app.config(['$resourceProvider', function($resourceProvider) {
        // Don't strip trailing slashes from calculated URLs
        $resourceProvider.defaults.stripTrailingSlashes = false;
    }]);

app.factory('CallResource', CallResource);
app.factory('CCOResource', CCOResource);
app.factory('ForecastDaysResource', ForecastDaysResource);
app.factory('MarketPricesResource', MarketPricesResource);
app.factory('OutgoingSMSResource', OutgoingSMSResource);
app.factory('IncomingSMSResource', IncomingSMSResource);

app.controller('CallCenterController', CallCenterController);
app.controller('MembersController', MembersController);
app.controller('CallQueueController', CallQueueController);
app.controller('InCallController', InCallController);

app.directive('ishambaleafletmap', LeafletMapDirective);
app.directive('weather', WeatherDirective);
app.directive('marketPrices', MarketPricesDirective);
app.directive('outgoingSms', OutgoingSMSDirective);
app.directive('incomingSms', IncomingSMSDirective);
