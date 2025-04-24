// A controller for the in-call view
// We need to watch hang events in case our call hangs up and for deque events
// to reload the connected calls if the current user did the dequeue

function activateDataUpdatesForm(customer) {
    // The "Data Updates Form" is used in the call interface for enabling CCO
    // to update important customer records.

    // Activate the form and title
    $('div#updates_title').show();
    $('form#updates_form').show();

    // Activate the necessary data update elements
    if (customer.sex === '') {
        $('div#div_id_gender').show();
    }
    if (!customer.border0 ||
        !customer.border1 ||
        !customer.border2 ||
        !customer.border3) {
        $('div#div_id_border0').show();
        $('div#div_id_border1').show();
        $('div#div_id_border2').show();
        $('div#div_id_border3').show();
    }
    // Set up the window globals and initial state
    if (typeof initializeLocationMenus !== 'undefined' && typeof initializeLocationMenus === "function") {
        initializeLocationMenus(false);
    }
}

function setDomVariable(id, value) {
    if (value !== undefined) {
        // Don't add undefined elements to the DOM
        let element = document.getElementById(id);
        if (!element) {
            // Create a new DOM script element and append it to the body
            element = document.createElement("script");
            element.id = id;
            element.type = 'application/json';
            document.body.appendChild(element);
        }
        element.textContent = JSON.stringify(value);
    }
}

function iShambaMapScriptLoaded(scope) {
    // One the leaflet script loads, make sure the map is initialized. Note: this
    // also happens asynchronously, so we don't want to override customer map
    // location if they have already been loaded.
    if (typeof window.iShambaGeoMap !== 'undefined' && typeof window.iShambaGeoMap.updateLeafletMapLayers === "function") {
        let map = window.iShambaGeoMap.getMap();
        if (!'border2pane' in map.getPanes() && !'border3pane' in map.getPanes()) {
            // If the leaflet map exists but is not yet initialized, set the customer's location
            let location = scope.call.customer.location;
            // {x: 34.604604375459836, y: -0.7592774741658361}
            if (!location || Object.keys(location) < 2) {
                location = null;
            } else {
                location = {
                    lng: location.x,
                    lat: location.y
                }
            }
            let resp_data = {
                'enableLeafletEditing': true,
                'customerId': scope.call.customer.id,
                'customerGPS': location,
            };
            if (scope.call.customer.border2) {
                resp_data['customerBorder2Label'] = scope.call.border2_label;
                resp_data['customerBorder2Name'] = scope.call.customer.border2.name;
                resp_data['customerBorder2Geometry'] = scope.call.customer.border2.border;
                resp_data['customerBorder2Centroid'] = scope.call.customer.border2.centroid;
            }
            if (scope.call.customer.border3) {
                resp_data['customerBorder3Label'] = scope.call.border3_label;
                resp_data['customerBorder3Name'] = scope.call.customer.border3.name;
                resp_data['customerBorder3Geometry'] = scope.call.customer.border3.border;
                resp_data['customerBorder3Centroid'] = scope.call.customer.border3.centroid;
            }
            window.iShambaGeoMap.updateLeafletMapLayers(resp_data, true);
        }
    }
}

let InCallController = ['$scope', '$http', 'CallResource', 'CCOResource', 'ForecastDaysResource', 'MarketPricesResource', 'OutgoingSMSResource', 'IncomingSMSResource', function($scope, $http, CallResource, CCOResource, ForecastDaysResource, MarketPricesResource, OutgoingSMSResource, IncomingSMSResource) {
    $scope.call = {};
    console.log("In call controller...");
    /*
     * Call, initialisation, customer
     */
    $scope.setCall = function(id) {
        // Update the global variables used by filter-form.js
        g_call_id = id;
        g_updates_url = '/calls/api/call/' + g_call_id + '/';
        var call = CallResource.get({id:id},
                function() {
                    var dirty = false;
                    if ($scope.callForm && $scope.callForm.$dirty) {
                        var notes = $scope.call.notes;
                        var resolved = $scope.call.issue_resolved;
                        dirty = true;
                    }
                    $scope.call = call;
                    if (dirty) {
                        $scope.call.notes = notes;
                        $scope.call.issue_resolved = resolved;
                    }

                    if (typeof window.iShambaGeoMap === 'undefined') {
                        // Set the DOM variables that iShambaGeoMap looks for
                        setDomVariable('enableLeafletEditing', true);
                        setDomVariable('customerId', $scope.call.customer.id);
                        let location = $scope.call.customer.location;
                        // {x: 34.604604375459836, y: -0.7592774741658361}
                        if (!location || Object.keys(location) < 2) {
                            location = null;
                        }
                        else {
                            location = {
                                lng: location.x,
                                lat: location.y
                            }
                        }
                        setDomVariable('customerGPS', JSON.stringify(location));
                        setDomVariable('customerBorder2Label', $scope.call.border2_label);
                        setDomVariable('customerBorder2Name', $scope.call.border2_name);
                        setDomVariable('customerBorder2Geometry', $scope.call.border2_geom);
                        setDomVariable('customerBorder2Centroid', $scope.call.border2_centroid);
                        setDomVariable('customerBorder3Label', $scope.call.border3_label);
                        setDomVariable('customerBorder3Name', $scope.call.border3_name);
                        setDomVariable('customerBorder3Geometry', $scope.call.border3_geom);
                        setDomVariable('customerBorder3Centroid', $scope.call.border3_centroid);

                        // Import our leaflet control javascript if necessary
                        let script = document.getElementById('ishamba_leaflet_script');
                        if (!script) {
                            script = document.createElement("script");
                            script.src = '/static/js/leaflet-controls.js?version=5';
                            script.id = 'ishamba_leaflet_script';
                            // Then bind the event to our map initialization callback function.
                            script.onload=()=>{
                                iShambaMapScriptLoaded($scope);
                            }
                            document.body.appendChild(script);
                        }
                    }
                    if (dataUpdatesNeeded($scope.call.customer)) {
                        activateDataUpdatesForm($scope.call.customer);
                    }
                    // Update the filter-form location fields
                    updateLocationMenusStates(false, call)
                    // Update the gender selection menu
                    let $el = $('select#id_gender')
                    if ($el.length && call['gender']) {
                        // If the element is on the page, and there is a data update from the server
                        $el.find('option[value=' + call['gender'] + ']').prop('selected', true);
                    }
                },
                function() {
                    alert("Error while trying to get active call for current user.");
                });
    }
    $scope.getCallFromCCO = function(cco_name) {
        $scope.cco = CCOResource.get({username: cco_name}, function() {
            if ($scope.cco.connected_call) {
                $scope.setCall($scope.cco.connected_call.id);
            }
        });
    }
    $scope.hangCallEvent = function(call_str) {
        console.log("Hanged call...");
        var call = JSON.parse(call_str.call);
        if(call.id == $scope.call.id) {
            // Our call was hanged
            $scope.$apply(function() {
                $scope.call.hanged_on = call.hanged_on;
                $scope.call.connected = call.connected;
            });
        }
    }
    $scope.dequeueCallEvent = function(call_str) {
        var call = JSON.parse(call_str.call);
        if(call.cco == g_username) {
            $scope.setCall(call.id);
        }
    }

    /*
     * Call saving
     */
    $scope.partial_update = function(obj, prop, oldValue) {
        // ignore the change event on initialisation
        if (typeof oldValue === 'undefined') return;
        // otherwise PATCH only the field in question
        params = {}
        params[prop] = obj[prop]
        obj.$partial_update(params, function(value) {
            // this may be inaccurate, as other fields may have changed
            $scope.callFormSetStatus('saved');
        });
    }
    $scope.$watch('call.notes', function(newValue, oldValue) {
        $scope.partial_update($scope.call, 'notes', oldValue);
    });
    $scope.$watch('call.issue_resolved', function(newValue, oldValue) {
        $scope.partial_update($scope.call, 'issue_resolved', oldValue);
    });
    $scope.callFormSetStatus = function (callFormStatus) {
        $scope.callFormStatus = callFormStatus;
    };
    $scope.callFormCheckStatus = function (callFormStatus) {
        return $scope.callFormStatus == callFormStatus;
    };

    /*
     * Outgoing SMS
     */
    $scope.setOutgoingSMSTab = function() {
        if (!$scope.outgoing_sms_messages) {
            $scope.getOutgoingSMS();
        }
        $scope.setTab('outgoing_sms');
    }
    $scope.getOutgoingSMS = function() {
        if (typeof $scope.outgoing_sms_messages === 'undefined') {
            $scope.outgoing_sms_messages = [];
        }
        OutgoingSMSResource.query({
                id:$scope.call.customer.id
            },
            function(data) {
                $scope.outgoing_sms_messages = data;
            },
            function() {
                alert("Unable to get customer's outgoing SMS records from server.");
            }
        );
    }

    /*
     * Incoming SMS
     */
    $scope.setIncomingSMSTab = function() {
        if (!$scope.incoming_sms_messages) {
            $scope.getIncomingSMS();
        }
        $scope.setTab('incoming_sms');
    }
    $scope.getIncomingSMS = function() {
        if (typeof $scope.incoming_sms_messages === 'undefined') {
            $scope.incoming_sms_messages = [];
        }
        IncomingSMSResource.query({
                id:$scope.call.customer.id
            },
            function(data) {
                $scope.incoming_sms_messages = data;
            },
            function() {
                alert("Unable to get customer's incoming SMS records from server.");
            }
        );
    }

    /*
     * Market Prices
     */
    $scope.setMarketPricesTab = function() {
        if (!$scope.market_prices) {
            $scope.getMarketPrices();
        }
        $scope.setTab('market_prices');
    }
    $scope.getMarketPrices = function() {
        if (typeof $scope.market_prices === 'undefined') {
            $scope.market_prices = {};
        }
        angular.forEach($scope.call.customer.market_subscriptions, function(value) {
            MarketPricesResource.query({
                    id:value.id
                },
                function(data) {
                    $scope.market_prices[value.name] = data;
                },
                // function() {
                //     alert("Unable to get " + value.name +" prices from server.");
                // }
            );
        });
    }

    /*
     * Weather
     */
    $scope.setWeatherTab = function() {
        if (!$scope.forecast_days) {
            $scope.getForecastDays();
        }
        $scope.setTab('weather');
    }
    $scope.getForecastDays = function(refresh) {
        ForecastDaysResource.query({
                id:$scope.call.customer.weather_area,
                refresh:refresh,
            },
            function(data) {
                $scope.forecast_days = data;
            },
            function() {
                alert("Unable to get weather from server.");
            }
        );
    }

    /*
     * Weather
     */
    $scope.setTab = function (tabId) {
        $scope.activeTab = tabId;
    };

    $scope.tabActive = function (tabId) {
        return this.activeTab === tabId;
    };

    /*
     * Go
     */
    $scope.getCallFromCCO(g_username);
    $scope.setTab('call');

    g_channel.bind(g_hang_call_event_name, $scope.hangCallEvent);
    g_channel.bind(g_connected_event_name, $scope.dequeueCallEvent);

    $scope.$on('$destroy', function() {
        // We need to unbind from the events because when router navigation occurs
        // angular will create a *new* CallQueueController which will *also*
        // bind to the same events !
        console.log("Destroy in call...");
        g_channel.unbind(g_hang_call_event_name, $scope.hangCallEvent);
        g_channel.unbind(g_connected_event_name, $scope.dequeueCallEvent);
    });
}];
