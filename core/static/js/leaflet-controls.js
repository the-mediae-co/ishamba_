// Create a global instance and assign it to the window context
window.iShambaGeoMap = (function(resp_data) {
    // Initialize the leaflet map
    const leafletMap = L.map('map');
    // Declare closure variables
    let customerId = null,
        initialCustomerGPS = null,
        customerGPS = null,
        initialCustomerBorder2Label = null,
        customerBorder2Label = null,
        initialCustomerBorder2Name = null,
        customerBorder2Name = null,
        initialCustomerBorder2Centroid = null,
        customerBorder2Centroid = null,
        initialCustomerBorder2Geometry = null,
        customerBorder2Geometry = null,
        initialCustomerBorder3Label = null,
        customerBorder3Label = null,
        initialCustomerBorder3Name = null,
        customerBorder3Name = null,
        initialCustomerBorder3Centroid = null,
        customerBorder3Centroid = null,
        initialCustomerBorder3Geometry = null,
        customerBorder3Geometry = null,
        initialSearchGeometry = null,
        border2Layer = null,
        border3Layer = null,
        centroidMarker = null,
        customerMarker = null,
        layerControl = null,
        resetControl = null,
        searchResultsLayer = null,
        enableLeafletEditing = false,
        linkMenusAndMap = true;

    const geocoderPromise = new Promise((resolve, reject)=>{
        let cssLoaded = false,
            jsLoaded = false;
        // Check if the geocoder has already been loaded
        let script = document.getElementById('leaflet_control_geocoder_script');
        if (script && L.Control.Geocoder !== undefined) {resolve();}
        // ...else load the geocoder css and js. We assume if one is missing, both are.
        // First load the css, then the js.
        let link = document.createElement('link');
        link.rel = "stylesheet";
        link.type="text/css";
        link.href = 'https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.css';
        // Notify when both have loaded
        link.onload=()=>{
            cssLoaded = true;
            if (cssLoaded && jsLoaded) {
                resolve();
            }
        }
        link.onerror=()=>{reject();}
        document.head.appendChild(link);
        script = document.createElement("script");
        script.src = 'https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.js';
        script.id = 'leaflet_control_geocoder_script';
        // Notify when both have loaded
        script.onload=()=>{
            jsLoaded = true;
            if (cssLoaded && jsLoaded) {
                resolve();
            }
        }
        script.onerror=()=>{reject();}
        document.body.appendChild(script);  // add it to the end of the body section of the page
    });
    // Initialize the search geocoder after it is loaded
    geocoderPromise.then((value) => {
        class iShambaSearch extends L.Control.Geocoder {
            handle(query, cb, context) {
                let url = '/world/search/';
                let push_data = [{name: 'query', value: query}];
                $.getJSON(url, push_data, resp_data => {
                    const results = [];
                    for (const match of resp_data['matches']) {
                        results.push({
                            name: match.name,
                            bbox: L.latLngBounds([match.bbox[1], match.bbox[0]], [match.bbox[3], match.bbox[2]]),
                            center: L.latLng(match.center),
                            border: JSON.parse(match.border),
                        });
                    }
                    cb.call(context, results);
                    if (results.length > 0) {
                        // Workaround a leaflet-control-geocoder bug
                        $('div.leaflet-control-geocoder-error')
                            .removeClass('leaflet-control-geocoder-error')
                    }
                }, "json");
            }
            // When return is pressed in the search field
            geocode(query, cb, context) {this.handle(query, cb, context);}
            // To give partial search results, this is called when text is being entered in the search field.
            suggest(query, cb, context) {this.handle(query, cb, context);}
        }
        let geoCoderOptions = {
            collapsed: true,
            defaultMarkGeocode: false,
            position: 'bottomleft',
            geocoder: new iShambaSearch(),
        }
        // Add search box
        L.Control.geocoder(geoCoderOptions)
            .on('markgeocode', function(e) {
                // Handler for when a search result is found
                // Update search results map layer
                if (searchResultsLayer) {
                    searchResultsLayer.clearLayers();
                }
                else {
                    // Initialize search results map layer (this should never happen)
                    leafletMap.createPane('searchResultsPane');
                    leafletMap.getPane('searchResultsPane').style.zIndex = 420;
                    searchResultsLayer = L.geoJSON(border2Feature, {style: searchResultsStyle, pane: 'searchResultsPane'}).addTo(leafletMap);
                }
                let search_border = e.geocode.border;
                if (search_border) {
                    searchResultsLayer.addData(search_border);
                }
                searchResultsLayer.bindTooltip(e.geocode.name);
                leafletMap.fitBounds(e.geocode.bbox);
            }).addTo(leafletMap);
        // Check if there's a generic border layer defined in the DOM that we need to draw
        let searchGeometry = extractDomData('search_geom', true);
        if (searchGeometry) {
            initialSearchGeometry = searchGeometry;
            searchResultsFeature['geometry'] = searchGeometry;
        }
        // Initialize search results map layer
        leafletMap.createPane('searchResultsPane');
        leafletMap.getPane('searchResultsPane').style.zIndex = 420;
        searchResultsLayer = L.geoJSON(searchResultsFeature, {
            style: searchResultsStyle,
            pane: 'searchResultsPane',
        }).addTo(leafletMap);
        let bounds = searchResultsLayer.getBounds();
        if (Object.keys(bounds).length > 0) {
            leafletMap.fitBounds(bounds);
        }
        layerControl.addOverlay(searchResultsLayer, 'Search');
        $('section.leaflet-control-layers-scrollbar').removeClass('leaflet-control-layers-scrollbar');
        leafletMap.invalidateSize();  // Redraw
    }, (error) => {console.log("ERROR LOADING: " + error)});

    function extractRespData(resp_data) {
        if (resp_data) {
            // Update the closure data with the customer values passed in
            customerBorder2Geometry = JSON.parse(resp_data['border2_geom']);
            customerBorder2Name = resp_data['border2_name'];
            customerBorder2Label = resp_data['border2_label'];
            customerBorder2Centroid = JSON.parse(resp_data['border2_centroid']);
            customerBorder3Geometry = JSON.parse(resp_data['border3_geom']);
            customerBorder3Name = resp_data['border3_name'];
            customerBorder3Label = resp_data['border3_label'];
            customerBorder3Centroid = JSON.parse(resp_data['border3_centroid']);
        }
    }
    function extractDomData(domId, doubleDecode) {
        let element = document.getElementById(domId);
        if (!element || element.length === 0) {
            return null;
        }
        let textContent = element.textContent;
        if (textContent && textContent.length > 0) {
            if (doubleDecode && typeof textContent === 'string') {
                textContent = JSON.parse(textContent);
            }
            if (textContent && textContent.length > 0) {
                return JSON.parse(textContent);
            }
        }
        return null;
    }

    if (resp_data) {
        extractRespData(resp_data);
    }
    else {
        // Otherwise try to retrieve the customer values from the DOM
        customerId = extractDomData('customerId');
        initialCustomerGPS = customerGPS = extractDomData('customerGPS', true);
        initialCustomerBorder2Label = customerBorder2Label = extractDomData('customerBorder2Label');
        initialCustomerBorder2Name = customerBorder2Name = extractDomData('customerBorder2Name');
        initialCustomerBorder2Geometry = customerBorder2Geometry = extractDomData('customerBorder2Geometry', true);
        initialCustomerBorder2Centroid = customerBorder2Centroid = extractDomData('customerBorder2Centroid', true);
        initialCustomerBorder3Label = customerBorder3Label = extractDomData('customerBorder3Label');
        initialCustomerBorder3Name = customerBorder3Name = extractDomData('customerBorder3Name');
        initialCustomerBorder3Geometry = customerBorder3Geometry = extractDomData('customerBorder3Geometry', true);
        initialCustomerBorder3Centroid = customerBorder3Centroid = extractDomData('customerBorder3Centroid', true);
        enableLeafletEditing = extractDomData('enableLeafletEditing');
        linkMenusAndMap = extractDomData('linkMenusAndMap');
    }

    // Define a new map control for resetting the view and customer's
    // location back to the state when initially loaded.
    let ResetView = L.Control.extend({
        options: {
            position: "topleft",
            title: "Reset view",
        },
        onAdd: function (map) {
            this._map = map;
            this._container = L.DomUtil.create("div", "leaflet-control-resetview leaflet-bar leaflet-control");
            this._link = L.DomUtil.create("a", "leaflet-bar-part leaflet-bar-part-single", this._container);
            this._link.title = this.options.title;
            // this._link.href = "#";
            this._link.setAttribute("role", "button");
            this._icon = L.DomUtil.create("span", "fa-solid fa-rotate-left", this._link);
            L.DomEvent.on(this._link, "click", this._resetView, this);
            return this._container;
        },
        onRemove: function (map) {
            L.DomEvent.off(this._link, "click", this._resetView, this);
        },
        _resetView: function (e) {
            customerGPS = initialCustomerGPS;
            customerBorder2Label = initialCustomerBorder2Label;
            customerBorder2Name = initialCustomerBorder2Name;
            customerBorder2Centroid = initialCustomerBorder2Centroid;
            customerBorder2Geometry = initialCustomerBorder2Geometry;
            customerBorder3Label = initialCustomerBorder3Label;
            customerBorder3Name = initialCustomerBorder3Name;
            customerBorder3Centroid = initialCustomerBorder3Centroid;
            customerBorder3Geometry = initialCustomerBorder3Geometry;
            if (customerMarker && initialCustomerGPS && leafletMap.hasLayer(customerMarker)) {
                customerMarker.setLatLng(initialCustomerGPS);
            }
            _updateBorderLayers();
            let b3bounds = border3Layer.getBounds();
            if (Object.keys(b3bounds) > 0) {
                this._map.fitBounds(b3bounds);
            }
            else if (searchResultsLayer) {
                searchResultsLayer.clearLayers();
                if (initialSearchGeometry) {
                    searchResultsLayer.addData(initialSearchGeometry);
                    let searchBounds = searchResultsLayer.getBounds();
                    if (Object.keys(searchBounds).length > 0) {
                        leafletMap.fitBounds(searchBounds);
                    }
                }
            }
            if (!customerGPS) {
                if (customerMarker && leafletMap.hasLayer(customerMarker)) {
                    customerMarker.remove();
                }
                $('form#updates_form input#id_lat').val('');
                $('form#updates_form input#id_lng').val('');
                let data = {
                    setCustomerToCentroid: false,
                    alreadyUpdatedMap: true,
                };
                let updates_form = document.getElementById('updates_form');
                if (updates_form) {
                    let locationChanged = new CustomEvent('change', {detail: data});
                    updates_form.dispatchEvent(locationChanged);
                }
            }
            else if (typeof updateLocationMenusStates === "function") {
                // Reset the location menus
                $.getJSON('/world/borders_for_location', customerGPS, function (resp_data) {
                    updateLocationMenusStates(false, resp_data);
                    // Fire an event to update the customer record on the server
                    let data = {
                        lat: customerGPS.lat,
                        lng: customerGPS.lng,
                        customer_id: customerId,
                        setCustomerToCentroid: false,
                        alreadyUpdatedMap: true,
                    };
                    let updates_form = document.getElementById('updates_form');
                    if (updates_form) {
                        let locationChanged = new CustomEvent('change', {detail: data});
                        updates_form.dispatchEvent(locationChanged);
                    }
                });
            }
            e.stopPropagation();
            e.preventDefault();
        },
    });

    // Set up defaults
    let border2Style = {
        color: "#faa307",
        fillColor: '#ffba08',
        fillOpacity: 0.3,
        opacity: 1.0,
        weight: 2,
    };
    let border3Style = {
        color: '#e85d04',
        fillColor: '#f48c06',
        fillOpacity: 0.4,
        opacity: 1.0,
        weight: 2,
    };
    let searchResultsStyle = {
        color: '#588157',
        fillColor: '#a7c957',
        fillOpacity: 0.3,
        opacity: 1.0,
        weight: 2,
    }
    let border2Feature = {
        type: "Feature",
        properties: { "name": customerBorder2Name },
        "geometry": customerBorder2Geometry,
    };
    let border3Feature = {
        type: "Feature",
        properties: { "name": customerBorder3Name },
        "geometry": customerBorder3Geometry,
    };
    let searchResultsFeature = {
        type: "Feature",
        properties: { "name": "Search Results" },
    };
    let customerMarkerOptions = {
        title: 'Customer',
        opacity: 0.8,
        draggable: enableLeafletEditing,
        autoPan: enableLeafletEditing,
    };
    let centroidMarkerOptions = {
        autoPan: false,
        color: '#9d0208',
        draggable: false,
        fill: true,
        fillColor: '#dc2f02',
        fillOpacity: 0.9,
        icon: null,
        interactive: false,
        opacity: 1.0,
        pane: 'centroidMarkerPane',
        radius: 4,
        weight: 1,
    };

    // Add a base layer for the openstreetmap overlay
    let streetMap = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(leafletMap);

    if (enableLeafletEditing) {
        // Set the default cursor for the <div> containing the map to be
        // crosshairs. When the mouse is moved into a different leaflet
        // layer (e.g. border3 multipolygon) leaflet changes it accordingly.
        leafletMap._container.style.cursor = 'crosshair';
    }
    // Create a separate pane to ride above the border3 pane and street map, but below the customer marker and shadow
    leafletMap.createPane('centroidMarkerPane');
    leafletMap.getPane('centroidMarkerPane').style.zIndex = 490;

    // Initially center the map on Nairobi (necessary to trigger "whenReady")
    leafletMap.setView([-1.304945593066499, 36.70052760999313], 6);

    leafletMap.whenReady((e) => {
        if (enableLeafletEditing) {
            // Register a click handler
            leafletMap.on('click', customerMarkerMoved);
        }
        if (customerGPS) {
            leafletMap.setView(customerGPS, 12);  // Position the map at the customer's location
            customerMarkerMoved();
        }
        else {
            leafletMap.setZoom(6);  // If no location, zoom the map out to the country level
        }

        // Initialize border2Layer
        border2Feature['geometry'] = customerBorder2Geometry;
        border2Feature['properties']['name'] = customerBorder2Name;
        leafletMap.createPane('border2pane');
        leafletMap.getPane('border2pane').style.zIndex = 440;
        border2Layer = L.geoJSON(border2Feature, {style: border2Style, pane: 'border2pane'}).addTo(leafletMap);

        // Initialize border3Layer
        border3Feature['geometry'] = customerBorder3Geometry;
        border3Feature['properties']['name'] = customerBorder3Name;
        leafletMap.createPane('border3pane');
        leafletMap.getPane('border3pane').style.zIndex = 450;
        border3Layer = L.geoJSON(border3Feature, {style: border3Style, pane: 'border3pane'}).addTo(leafletMap);

        resetControl = new ResetView({
            position: "topleft",
            title: "Reset view",
            pointerEvents: 'auto',
        }).addTo(leafletMap);

        layerControl = L.control.layers(
            {'map': streetMap},
            {},
            {'hideSingleBase': true, 'collapsed': false, 'autoZIndex': false}
        ).addTo(leafletMap);

        // Enable the controls, regardless of whether we know the customer's location
        if (customerBorder2Label) {
            layerControl.addOverlay(border2Layer, customerBorder2Label);
        }
        if (customerBorder3Label) {
            layerControl.addOverlay(border3Layer, customerBorder3Label);
        }

        // Give border2 and border3 geometries their proper tooltips, center map to the customer's location, etc.
        _updateBorderLayers()
    });

    function customerMarkerMoved(e) {
        if (e && e.target !== this) {
            // If not intended for us, exit
            return;
        }

        // Default to the customer's currently marked location
        let latlng = customerGPS;
        if (e && e.type === 'click') {
            latlng = e.latlng;
        } else if (e && e.type === 'dragend') {
            latlng = e.target.getLatLng();
        }

        if (!customerMarker) {
            // First time setting the marker so position the map at the customer's location
            leafletMap.setView(latlng, 13);
            customerMarker = L.marker(latlng, customerMarkerOptions).addTo(leafletMap);
            if (enableLeafletEditing) {
                customerMarker.on('dragend', customerMarkerMoved);
            }
            _updateBorderLayers();
        }

        // Either the ward was changed via menu or the user clicked or dragged to this location
        if (!leafletMap.hasLayer(customerMarker)) {
            customerMarker.addTo(leafletMap);
        }
        customerMarker.setLatLng(latlng);
        if (e) {
            $('form#updates_form input#id_lat').val(latlng.lat);
            $('form#updates_form input#id_lng').val(latlng.lng);
            let action_loc = $('form').attr('action');
            if (action_loc && (action_loc === '/management/bulk_sms/' || action_loc.startsWith('/offers/'))) {
                // Submit the new lat/lng to the server to get an updated customer count
                let data = {
                    setCustomerToCentroid: false,
                    alreadyUpdatedMap: true,
                    linkMenusAndMap: linkMenusAndMap,
                };
                let updates_form = document.getElementById('updates_form');
                if (updates_form) {
                    let locationChanged = new CustomEvent('change', {detail: data});
                    updates_form.dispatchEvent(locationChanged);
                }
            }
            else {
                // The user clicked or dragged. If not, we just got a border menu update so no need to fetch another
                let data = {'lat': latlng['lat'], 'lng': latlng['lng'], 'customer_id': customerId};
                $.getJSON('/world/borders_for_location', data, function (resp_data) {
                    _updateBorderLayers(resp_data, false);
                    if (typeof updateLocationMenusStates === "function") {
                        updateLocationMenusStates(false, resp_data);
                        // Fire an event to update the customer record on the server
                        data.setCustomerToCentroid = false;
                        data.alreadyUpdatedMap = true;
                        data.linkMenusAndMap = linkMenusAndMap;
                        let updates_form = document.getElementById('updates_form');
                        if (updates_form) {
                            let locationChanged = new CustomEvent('change', {detail: data});
                            updates_form.dispatchEvent(locationChanged);
                        }
                    }
                });
            }
        }

        // In any case, set the map location and zoom to cover the border3
        if (border3Layer && leafletMap.hasLayer(border3Feature)) {
            let b3bounds = border3Layer.getBounds();
            if (Object.keys(b3bounds).length > 0) {
                leafletMap.fitBounds(b3bounds);
            }
        }
    }

    function _updateBorderLayers(resp_data=null, setCustomerToCentroid=false) {
        if (resp_data && resp_data['border3_geom']) {
            // Update the closure data
            extractRespData(resp_data);
            if (setCustomerToCentroid) {
                // django and leaflet use the opposite order for lat/long
                customerGPS = {'lat': customerBorder3Centroid.coordinates[1], 'lng': customerBorder3Centroid.coordinates[0]};
                customerMarkerMoved();
            }
        }
        else if (resp_data) {
            // No border geometries
            customerBorder2Name = customerBorder2Label = customerBorder2Geometry = customerBorder2Centroid = null;
            customerBorder3Name = customerBorder3Label = customerBorder3Geometry = customerBorder3Centroid = null;
            if (border2Layer) {
                border2Layer.clearLayers();
            }
            if (border3Layer) {
                border3Layer.clearLayers();
            }
            if (centroidMarker) {
                centroidMarker.remove();
            }
            if (customerMarker && $('form').attr('action') !== '/management/bulk_sms/') {
                customerMarker.remove();
            }
            return;
        }

        // Update border2 layer
        if (border2Layer) {
            border2Layer.clearLayers();
            if (customerBorder2Geometry) {
                border2Layer.addData(customerBorder2Geometry);
            }
            border2Layer.bindTooltip(customerBorder2Label + ': ' + customerBorder2Name);
        }

        // Update border3 layer
        if (border3Layer) {
            border3Layer.clearLayers();
            if (customerBorder3Geometry) {
                border3Layer.addData(customerBorder3Geometry);
            }
            border3Layer.bindTooltip(customerBorder3Label + ': ' + customerBorder3Name);
            border3Layer.openTooltip();
        }

        // Update markers
        if (centroidMarker) {
            centroidMarker.remove();
        }
        if (customerBorder3Centroid) {
            centroidMarker = L.circleMarker(
                [customerBorder3Centroid.coordinates[1], customerBorder3Centroid.coordinates[0]],
                centroidMarkerOptions
            ).addTo(leafletMap);
        }
        // If the border3 geometry is not fully visible, adjust the map location and zoom
        if (border3Layer && leafletMap.hasLayer(border3Layer)) {
            let b3bounds = border3Layer.getBounds();
            if (Object.keys(b3bounds).length > 0) {
                let fullyVisible = leafletMap.getBounds().contains(b3bounds);
                if (!fullyVisible) {
                    leafletMap.fitBounds(b3bounds);
                }
            }
        }
    }

    return {
        setCustomerId(id) {
            customerId = id;
        },
        setCustomerGPS(latlng) {
            customerGPS = latlng;
            customerMarkerMoved();
        },
        setCustomerBorder2(border2Name, border2Label, border2Centroid, border2Geometry) {
            customerBorder2Name = border2Name;
            customerBorder2Label = border2Label;
            customerBorder2Centroid = border2Centroid;
            customerBorder2Geometry = border2Geometry;
            _updateBorderLayers();
        },
        setCustomerBorder3(border3Name, border3Label, border3Centroid, border3Geometry) {
            customerBorder3Name = border3Name;
            customerBorder3Label = border3Label;
            customerBorder3Centroid = border3Centroid;
            customerBorder3Geometry = border3Geometry;
            _updateBorderLayers();
        },
        updateLeafletMapLayers(resp_data, setCustomerToCentroid=false) {
            _updateBorderLayers(resp_data, setCustomerToCentroid)
        },
        getMap() {
            return leafletMap;
        }
    }
})();
