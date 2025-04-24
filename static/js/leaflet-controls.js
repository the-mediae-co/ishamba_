// Create a global instance and assign it to the window context
window.iShambaGeoMap = (function() {
    // Initialize the leaflet map
    const leafletMap = L.map('map');

    // Declare closure variables for state management
    let customerId = null,
        customerGPS = null,
        initialCustomerGPS = null,
        customerBorder2Label = null,
        initialCustomerBorder2Label = null,
        customerBorder2Name = null,
        initialCustomerBorder2Name = null,
        customerBorder2Centroid = null,
        initialCustomerBorder2Centroid = null,
        customerBorder2Geometry = null,
        initialCustomerBorder2Geometry = null,
        customerBorder3Label = null,
        initialCustomerBorder3Label = null,
        customerBorder3Name = null,
        initialCustomerBorder3Name = null,
        customerBorder3Centroid = null,
        initialCustomerBorder3Centroid = null,
        customerBorder3Geometry = null,
        initialCustomerBorder3Geometry = null,
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

    // Style definitions for map layers
    const border2Style = {
        color: "#faa307",
        fillColor: '#ffba08',
        fillOpacity: 0.3,
        opacity: 1.0,
        weight: 2,
    };

    const border3Style = {
        color: '#e85d04',
        fillColor: '#f48c06',
        fillOpacity: 0.4,
        opacity: 1.0,
        weight: 2,
    };

    const searchResultsStyle = {
        color: '#588157',
        fillColor: '#a7c957',
        fillOpacity: 0.3,
        opacity: 1.0,
        weight: 2,
    };

    // Feature definitions for GeoJSON layers
    const border2Feature = {
        type: "Feature",
        properties: { "name": "" },
        geometry: null
    };

    const border3Feature = {
        type: "Feature",
        properties: { "name": "" },
        geometry: null
    };

    const searchResultsFeature = {
        type: "Feature",
        properties: { "name": "Search Results" },
        geometry: null
    };

    // Marker options
    const customerMarkerOptions = {
        title: 'Customer',
        opacity: 0.8,
        draggable: false, // Will be updated based on enableLeafletEditing
        autoPan: false,   // Will be updated based on enableLeafletEditing
    };

    const centroidMarkerOptions = {
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

    // Helper function to safely extract data from DOM elements
    function extractDomData(domId, doubleDecode = false) {
        try {
            const element = document.getElementById(domId);
            if (!element || !element.textContent) {
                return null;
            }

            let textContent = element.textContent.trim();
            if (!textContent) {
                return null;
            }

            if (doubleDecode && typeof textContent === 'string') {
                try {
                    textContent = JSON.parse(textContent);
                } catch (e) {
                    console.error(`Error parsing first level JSON from ${domId}:`, e);
                    return null;
                }
            }

            if (textContent) {
                try {
                    return JSON.parse(textContent);
                } catch (e) {
                    console.error(`Error parsing ${doubleDecode ? 'second level' : ''} JSON from ${domId}:`, e);
                    return null;
                }
            }

            return null;
        } catch (e) {
            console.error(`Error extracting data from element ${domId}:`, e);
            return null;
        }
    }

    // Function to extract data from response object
    function extractRespData(resp_data) {
        if (!resp_data) return false;

        try {
            // Update the closure data with the response values
            if (resp_data.border2_geom) {
                customerBorder2Geometry = typeof resp_data.border2_geom === 'string' ?
                    JSON.parse(resp_data.border2_geom) : resp_data.border2_geom;
            }

            customerBorder2Name = resp_data.border2_name || "";
            customerBorder2Label = resp_data.border2_label || "";

            if (resp_data.border2_centroid) {
                customerBorder2Centroid = typeof resp_data.border2_centroid === 'string' ?
                    JSON.parse(resp_data.border2_centroid) : resp_data.border2_centroid;
            }

            if (resp_data.border3_geom) {
                customerBorder3Geometry = typeof resp_data.border3_geom === 'string' ?
                    JSON.parse(resp_data.border3_geom) : resp_data.border3_geom;
            }

            customerBorder3Name = resp_data.border3_name || "";
            customerBorder3Label = resp_data.border3_label || "";

            if (resp_data.border3_centroid) {
                customerBorder3Centroid = typeof resp_data.border3_centroid === 'string' ?
                    JSON.parse(resp_data.border3_centroid) : resp_data.border3_centroid;
            }

            return true;
        } catch (e) {
            console.error("Error extracting response data:", e);
            return false;
        }
    }

    // Initialize data from parameters or DOM
    function initializeData(resp_data) {
        if (resp_data) {
            extractRespData(resp_data);
        } else {
            // Try to retrieve values from the DOM
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

            // Get configuration options
            enableLeafletEditing = extractDomData('enableLeafletEditing') || false;
            linkMenusAndMap = extractDomData('linkMenusAndMap') !== false; // Default to true

            // Update marker options based on editing settings
            customerMarkerOptions.draggable = enableLeafletEditing;
            customerMarkerOptions.autoPan = enableLeafletEditing;
        }

        // Check for search geometry
        initialSearchGeometry = extractDomData('search_geom', true);
        if (initialSearchGeometry) {
            searchResultsFeature.geometry = initialSearchGeometry;
        }
    }

    // Custom Reset View control
    const ResetView = L.Control.extend({
        options: {
            position: "topleft",
            title: "Reset view",
        },

        onAdd: function(map) {
            this._map = map;
            this._container = L.DomUtil.create("div", "leaflet-control-resetview leaflet-bar leaflet-control");
            this._link = L.DomUtil.create("a", "leaflet-bar-part leaflet-bar-part-single", this._container);
            this._link.title = this.options.title;
            this._link.setAttribute("role", "button");
            this._icon = L.DomUtil.create("span", "fa-solid fa-rotate-left", this._link);

            L.DomEvent.on(this._link, "click", this._resetView, this);
            return this._container;
        },

        onRemove: function(map) {
            L.DomEvent.off(this._link, "click", this._resetView, this);
        },

        _resetView: function(e) {
            if (e) {
                L.DomEvent.preventDefault(e);
                L.DomEvent.stopPropagation(e);
            }

            // Reset state to initial values
            customerGPS = initialCustomerGPS;
            customerBorder2Label = initialCustomerBorder2Label;
            customerBorder2Name = initialCustomerBorder2Name;
            customerBorder2Centroid = initialCustomerBorder2Centroid;
            customerBorder2Geometry = initialCustomerBorder2Geometry;
            customerBorder3Label = initialCustomerBorder3Label;
            customerBorder3Name = initialCustomerBorder3Name;
            customerBorder3Centroid = initialCustomerBorder3Centroid;
            customerBorder3Geometry = initialCustomerBorder3Geometry;

            // Update marker position if it exists
            if (customerMarker && initialCustomerGPS && leafletMap.hasLayer(customerMarker)) {
                customerMarker.setLatLng(initialCustomerGPS);
            }

            // Update border layers
            updateBorderLayers();

            // Adjust map bounds
            let bounds;
            if (border3Layer) {
                bounds = border3Layer.getBounds();
                if (bounds.isValid()) {
                    this._map.fitBounds(bounds);
                }
            } else if (searchResultsLayer) {
                searchResultsLayer.clearLayers();
                if (initialSearchGeometry) {
                    searchResultsLayer.addData(initialSearchGeometry);
                    bounds = searchResultsLayer.getBounds();
                    if (bounds.isValid()) {
                        leafletMap.fitBounds(bounds);
                    }
                }
            }

            // Update form fields and trigger events
            if (!customerGPS) {
                if (customerMarker && leafletMap.hasLayer(customerMarker)) {
                    customerMarker.remove();
                }

                $('form#updates_form input#id_lat').val('');
                $('form#updates_form input#id_lng').val('');

                triggerUpdateEvent({
                    setCustomerToCentroid: false,
                    alreadyUpdatedMap: true
                });
            } else if (typeof updateLocationMenusStates === "function") {
                // Reset the location menus
                fetchBordersForLocation(customerGPS, function(resp_data) {
                    if (resp_data) {
                        updateLocationMenusStates(false, resp_data);

                        triggerUpdateEvent({
                            lat: customerGPS.lat,
                            lng: customerGPS.lng,
                            customer_id: customerId,
                            setCustomerToCentroid: false,
                            alreadyUpdatedMap: true
                        });
                    }
                });
            }
        }
    });

    // Helper function to trigger form update events
    function triggerUpdateEvent(detail) {
        const updates_form = document.getElementById('updates_form');
        if (updates_form) {
            const locationChanged = new CustomEvent('change', { detail: detail });
            updates_form.dispatchEvent(locationChanged);
        }
    }

    // Function to fetch borders for a location
    function fetchBordersForLocation(latlng, callback) {
        if (!latlng || !latlng.lat || !latlng.lng) {
            console.error("Invalid coordinates for borders lookup");
            if (typeof callback === 'function') callback(null);
            return;
        }

        const data = {
            'lat': latlng.lat,
            'lng': latlng.lng,
            'customer_id': customerId
        };

        $.ajax({
            url: '/world/borders_for_location',
            data: data,
            dataType: 'json',
            success: function(resp_data) {
                if (typeof callback === 'function') {
                    callback(resp_data);
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("Error fetching borders:", textStatus, errorThrown);
                if (typeof callback === 'function') {
                    callback(null);
                }
            }
        });
    }

    // Function to handle customer marker movement
    function customerMarkerMoved(e) {
        let latlng = customerGPS;

        // Get coordinates from the event if available
        if (e) {
            if (e.type === 'click') {
                latlng = e.latlng;
            } else if (e.type === 'dragend' && e.target) {
                latlng = e.target.getLatLng();
            }
        }

        // Exit if we don't have valid coordinates
        if (!latlng || !latlng.lat || !latlng.lng) {
            return;
        }

        // Create the marker if it doesn't exist
        if (!customerMarker) {
            leafletMap.setView(latlng, 13);
            customerMarker = L.marker(latlng, customerMarkerOptions).addTo(leafletMap);

            if (enableLeafletEditing) {
                customerMarker.on('dragend', customerMarkerMoved);
            }

            updateBorderLayers();
        } else {
            // Update existing marker
            if (!leafletMap.hasLayer(customerMarker)) {
                customerMarker.addTo(leafletMap);
            }
            customerMarker.setLatLng(latlng);
        }

        // Update form values if this was triggered by a user action
        if (e) {
            // Update form fields
            $('form#updates_form input#id_lat').val(latlng.lat);
            $('form#updates_form input#id_lng').val(latlng.lng);

            // Check if we need to update the server
            const action_loc = $('form').attr('action');
            if (action_loc && (action_loc === '/management/bulk_sms/' || action_loc.startsWith('/offers/'))) {
                // Submit directly to update customer count
                triggerUpdateEvent({
                    setCustomerToCentroid: false,
                    alreadyUpdatedMap: true,
                    linkMenusAndMap: linkMenusAndMap
                });
            } else {
                // Fetch updated border information
                // Fetch updated border information
                fetchBordersForLocation(latlng, function(resp_data) {
                    // Update map layers with new border data
                    updateBorderLayers(resp_data, false);

                    // Update UI menus if the function exists
                    if (typeof updateLocationMenusStates === "function") {
                        updateLocationMenusStates(false, resp_data);

                        // Trigger update event for the server
                        const updateData = {
                            lat: latlng.lat,
                            lng: latlng.lng,
                            customer_id: customerId,
                            setCustomerToCentroid: false,
                            alreadyUpdatedMap: true,
                            linkMenusAndMap: linkMenusAndMap
                        };

                        triggerUpdateEvent(updateData);
                    }
                });
            }
        }

        // Fit the map to the border3 layer if available
        if (border3Layer && leafletMap.hasLayer(border3Layer)) {
            const bounds = border3Layer.getBounds();
            if (bounds.isValid()) {
                leafletMap.fitBounds(bounds);
            }
        }
    }

    // Function to update border layers
    function updateBorderLayers(resp_data = null, setCustomerToCentroid = false) {
        // Process new data if provided
        if (resp_data) {
            const dataExtracted = extractRespData(resp_data);

            if (setCustomerToCentroid && customerBorder3Centroid && customerBorder3Centroid.coordinates) {
                // Update customer position to centroid
                customerGPS = {
                    lat: customerBorder3Centroid.coordinates[1],
                    lng: customerBorder3Centroid.coordinates[0]
                };
                customerMarkerMoved();
            }

            // If no borders were found and we've extracted data, clear layers
            if (!dataExtracted || (!customerBorder2Geometry && !customerBorder3Geometry)) {
                // No border geometries - clear everything
                customerBorder2Name = customerBorder2Label = "";
                customerBorder2Geometry = customerBorder2Centroid = null;
                customerBorder3Name = customerBorder3Label = "";
                customerBorder3Geometry = customerBorder3Centroid = null;

                if (border2Layer) {
                    border2Layer.clearLayers();
                }

                if (border3Layer) {
                    border3Layer.clearLayers();
                }

                if (centroidMarker) {
                    centroidMarker.remove();
                }

                // Only remove customer marker if not in bulk SMS mode
                if (customerMarker && $('form').attr('action') !== '/management/bulk_sms/') {
                    customerMarker.remove();
                }

                return;
            }
        }

        // Update border2 layer
        if (border2Layer) {
            border2Layer.clearLayers();

            if (customerBorder2Geometry) {
                try {
                    border2Feature.geometry = customerBorder2Geometry;
                    border2Feature.properties.name = customerBorder2Name || "";
                    border2Layer.addData(border2Feature);

                    if (customerBorder2Label && customerBorder2Name) {
                        border2Layer.bindTooltip(`${customerBorder2Label}: ${customerBorder2Name}`);
                    }
                } catch (e) {
                    console.error("Error updating border2 layer:", e);
                }
            }
        }

        // Update border3 layer
        if (border3Layer) {
            border3Layer.clearLayers();

            if (customerBorder3Geometry) {
                try {
                    border3Feature.geometry = customerBorder3Geometry;
                    border3Feature.properties.name = customerBorder3Name || "";
                    border3Layer.addData(border3Feature);

                    if (customerBorder3Label && customerBorder3Name) {
                        border3Layer.bindTooltip(`${customerBorder3Label}: ${customerBorder3Name}`);
                        border3Layer.openTooltip();
                    }
                } catch (e) {
                    console.error("Error updating border3 layer:", e);
                }
            }
        }

        // Update centroid marker
        if (centroidMarker) {
            centroidMarker.remove();
        }

        if (customerBorder3Centroid && customerBorder3Centroid.coordinates) {
            try {
                centroidMarker = L.circleMarker(
                    [customerBorder3Centroid.coordinates[1], customerBorder3Centroid.coordinates[0]],
                    centroidMarkerOptions
                ).addTo(leafletMap);
            } catch (e) {
                console.error("Error creating centroid marker:", e);
            }
        }

        // Adjust map view if border3 isn't fully visible
        if (border3Layer && leafletMap.hasLayer(border3Layer)) {
            const bounds = border3Layer.getBounds();
            if (bounds.isValid()) {
                const mapBounds = leafletMap.getBounds();
                const fullyVisible = mapBounds.contains(bounds);

                if (!fullyVisible) {
                    leafletMap.fitBounds(bounds);
                }
            }
        }
    }

    // Function to initialize the custom search control
    function initializeSearchControl() {
        // Create a custom search control
        const CustomSearchControl = L.Control.extend({
            options: {
                position: 'bottomleft'
            },

            onAdd: function(map) {
                const container = L.DomUtil.create('div', 'custom-search-control leaflet-control');
                container.innerHTML = `
                    <form class="custom-search-form">
                        <input type="text" placeholder="Search locations..." class="custom-search-input">
                        <button type="submit" class="custom-search-button">
                            <i class="fa fa-search"></i>
                        </button>
                    </form>
                `;

                // Prevent map events from firing when interacting with the control
                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);

                // Handle form submission
                const form = container.querySelector('form');
                L.DomEvent.on(form, 'submit', function(e) {
                    e.preventDefault();

                    const input = container.querySelector('input');
                    const query = input ? input.value.trim() : '';

                    if (query) {
                        performSearch(query);
                    }

                    return false;
                });

                return container;
            }
        });

        // Add the search control to the map
        new CustomSearchControl().addTo(leafletMap);

        // Create or update search results layer
        if (!searchResultsLayer) {
            leafletMap.createPane('searchResultsPane');
            leafletMap.getPane('searchResultsPane').style.zIndex = 420;

            searchResultsLayer = L.geoJSON(searchResultsFeature, {
                style: searchResultsStyle,
                pane: 'searchResultsPane'
            }).addTo(leafletMap);

            // Add to layer control if it exists
            if (layerControl) {
                layerControl.addOverlay(searchResultsLayer, 'Search');
            }
        }
    }

    // Function to perform location search
    function performSearch(query) {
        if (!query) return;

        $.ajax({
            url: '/world/search/',
            data: { query: query },
            dataType: 'json',
            success: function(resp_data) {
                try {
                    // Clear previous search results
                    if (searchResultsLayer) {
                        searchResultsLayer.clearLayers();
                    }

                    // Process search results
                    if (resp_data && resp_data.matches && resp_data.matches.length > 0) {
                        const match = resp_data.matches[0]; // Use first match

                        // Create bounding box for the result
                        if (match.bbox && match.bbox.length >= 4) {
                            const bounds = L.latLngBounds(
                                [match.bbox[1], match.bbox[0]],
                                [match.bbox[3], match.bbox[2]]
                            );

                            // Add border geometry if available
                            if (match.border) {
                                let borderData;
                                try {
                                    borderData = typeof match.border === 'string' ?
                                        JSON.parse(match.border) : match.border;

                                    searchResultsLayer.addData(borderData);

                                    if (match.name) {
                                        searchResultsLayer.bindTooltip(match.name);
                                    }
                                } catch (e) {
                                    console.error("Error parsing search result border:", e);
                                }
                            }

                            // Zoom to the bounds
                            leafletMap.fitBounds(bounds);
                        }
                    } else {
                        console.log("No search results found");
                    }
                } catch (e) {
                    console.error("Error processing search results:", e);
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("Search request failed:", textStatus, errorThrown);
            }
        });
    }

    // Function to initialize map
    function initializeMap(resp_data) {
        // Initialize data from parameters or DOM
        initializeData(resp_data);

        // Add base layer (OpenStreetMap)
        const streetMap = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(leafletMap);

        // Set cursor style if editing is enabled
        if (enableLeafletEditing) {
            leafletMap._container.style.cursor = 'crosshair';
        }

        // Create centroid marker pane
        leafletMap.createPane('centroidMarkerPane');
        leafletMap.getPane('centroidMarkerPane').style.zIndex = 490;

        // Initially center the map (will be updated later)
        leafletMap.setView([-1.304945593066499, 36.70052760999313], 6);

        // Set up map when ready
        leafletMap.whenReady(function() {
            // Register click handler if editing is enabled
            if (enableLeafletEditing) {
                leafletMap.on('click', customerMarkerMoved);
            }

            // Position map at customer location if available
            if (customerGPS) {
                leafletMap.setView(customerGPS, 12);
                customerMarkerMoved();
            } else {
                leafletMap.setZoom(6);
            }

            // Initialize border2 layer
            leafletMap.createPane('border2pane');
            leafletMap.getPane('border2pane').style.zIndex = 440;

            border2Feature.geometry = customerBorder2Geometry;
            border2Feature.properties.name = customerBorder2Name || "";

            border2Layer = L.geoJSON(border2Feature, {
                style: border2Style,
                pane: 'border2pane'
            }).addTo(leafletMap);

            // Initialize border3 layer
            leafletMap.createPane('border3pane');
            leafletMap.getPane('border3pane').style.zIndex = 450;

            border3Feature.geometry = customerBorder3Geometry;
            border3Feature.properties.name = customerBorder3Name || "";

            border3Layer = L.geoJSON(border3Feature, {
                style: border3Style,
                pane: 'border3pane'
            }).addTo(leafletMap);

            // Add reset control
            resetControl = new ResetView({
                position: "topleft",
                title: "Reset view"
            }).addTo(leafletMap);

            // Create layer control
            layerControl = L.control.layers(
                { 'Map': streetMap },
                {},
                { 'hideSingleBase': true, 'collapsed': false, 'autoZIndex': false }
            ).addTo(leafletMap);

            // Add overlays to layer control
            if (customerBorder2Label) {
                layerControl.addOverlay(border2Layer, customerBorder2Label);
            }

            if (customerBorder3Label) {
                layerControl.addOverlay(border3Layer, customerBorder3Label);
            }

            // Initialize search control
            initializeSearchControl();

            // Update border layers with initial data
            updateBorderLayers();
        });
    }

    // Initialize the map with provided data
    initializeMap(arguments[0]);

    // Return public API
    return {
        setCustomerId: function(id) {
            customerId = id;
        },

        setCustomerGPS: function(latlng) {
            if (!latlng || typeof latlng.lat === 'undefined' || typeof latlng.lng === 'undefined') {
                console.error("Invalid GPS coordinates");
                return;
            }

            customerGPS = latlng;
            customerMarkerMoved();
        },

        setCustomerBorder2: function(border2Name, border2Label, border2Centroid, border2Geometry) {
            customerBorder2Name = border2Name || "";
            customerBorder2Label = border2Label || "";
            customerBorder2Centroid = border2Centroid;
            customerBorder2Geometry = border2Geometry;
            updateBorderLayers();
        },

        setCustomerBorder3: function(border3Name, border3Label, border3Centroid, border3Geometry) {
            customerBorder3Name = border3Name || "";
            customerBorder3Label = border3Label || "";
            customerBorder3Centroid = border3Centroid;
            customerBorder3Geometry = border3Geometry;
            updateBorderLayers();
        },

        updateLeafletMapLayers: function(resp_data, setCustomerToCentroid = false) {
            updateBorderLayers(resp_data, setCustomerToCentroid);
        },

        getMap: function() {
            return leafletMap;
        }
    };
})();