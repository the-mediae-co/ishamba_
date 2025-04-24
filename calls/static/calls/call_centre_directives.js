var WeatherDirective = function() {
    return {
        restrict: 'A',
        templateUrl: g_in_call_weather_template,
        //scope: {
        //    'forecast_days': "=forecast_days"
        //},
        link: function($scope, $element, $attrs) {
        }
    };
};

var OutgoingSMSDirective = function() {
    return {
        restrict: 'A',
        templateUrl: g_in_call_outgoing_sms_template,
    };
};

var IncomingSMSDirective = function() {
    return {
        restrict: 'A',
        templateUrl: g_in_call_incoming_sms_template,
    };
};

var MarketPricesDirective = function() {
    return {
        restrict: 'A',
        templateUrl: g_in_call_market_prices_template,
    };
};

var LeafletMapDirective = function() {
    return {
        restrict: 'E',
        template: '<div id="map" style="height: 360px;"></div>',
        replace: true,
        link: function(scope, elem, attrs) {
            // A function to watch for when the map becomes visible, so it can be invalidated
            function onVisible(element, callback) {
                new IntersectionObserver((entries, observer) => {
                    entries.forEach(entry => {
                        if(entry.intersectionRatio > 0) {
                            callback(element);
                            observer.disconnect();
                        }
                    });
                }).observe(element);
            }

            // Fire an event when the div is created
            let mapDivCreated = new Event('mapDivCreated');
            window.dispatchEvent(mapDivCreated);

            // Watch for when the customer data for this call gets loaded,
            // and then load the leaflet map code if it hasn't been already.
            scope.$watch("call.customer", function(customer, oldValue) {
                if (customer) {
                    // Import our leaflet control javascript if necessary
                    let script = document.getElementById('ishamba_leaflet_script');
                    if (!script) {
                        script = document.createElement("script");
                        script.src = '/static/js/leaflet-controls.js?version=5';
                        script.id = 'ishamba_leaflet_script';
                        // Then bind the event to our map initialization callback function.
                        script.onload=()=>{
                            iShambaMapScriptLoaded(scope);
                        }
                        document.body.appendChild(script);
                    }
                }
            });
            // When the leaflet map becomes visible, we need to invalidate it so that it refreshes
            onVisible(document.querySelector("#map"),()=>{
                if (typeof window.iShambaGeoMap !== 'undefined' && typeof window.iShambaGeoMap.getMap === "function") {
                    window.iShambaGeoMap.getMap().invalidateSize();
                }
            });
        }
    };
};
