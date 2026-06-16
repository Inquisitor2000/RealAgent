"""
Interactive Map Overlay for Address Correction
==============================================

This module provides an interactive OpenStreetMap overlay that allows users
to click on a location to get precise coordinates and address information
when geocoding confidence is low.

Dependencies:
- folium: For interactive map generation
- webbrowser: For opening map in browser
- http.server: For serving the map locally
"""

import folium
import webbrowser
import tempfile
import os
import json
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import socket
from pathlib import Path

class MapOverlayServer:
    """HTTP server to handle map interactions and coordinate selection."""
    
    def __init__(self):
        self.selected_coordinates = None
        self.selected_address = None
        self.server = None
        self.server_thread = None
        self.port = None
        
    def find_free_port(self):
        """Find a free port for the HTTP server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def start_server(self, temp_dir):
        """Start HTTP server to serve the map and handle coordinate selection."""
        self.port = self.find_free_port()
        
        class MapHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=temp_dir, **kwargs)
            
            def do_POST(self):
                """Handle coordinate selection from the map."""
                if self.path == '/select_coordinates':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    # Store the selected coordinates and address
                    server_instance.selected_coordinates = (data['lat'], data['lng'])
                    server_instance.selected_address = data.get('address', 'Selected location')
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
                else:
                    self.send_error(404)
            
            def log_message(self, format, *args):
                """Suppress server logs."""
                pass
        
        server_instance = self
        self.server = HTTPServer(('127.0.0.1', self.port), MapHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        return f"http://127.0.0.1:{self.port}"
    
    def stop_server(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread:
            self.server_thread.join(timeout=1)

def create_interactive_map(original_address, estimated_lat=47.0105, estimated_lng=28.8638):
    """
    Create an interactive map for address correction.
    
    Args:
        original_address: The original address that needs correction
        estimated_lat: Estimated latitude (defaults to Chișinău center)
        estimated_lng: Estimated longitude (defaults to Chișinău center)
    
    Returns:
        tuple: (latitude, longitude, corrected_address) or None if cancelled
    """
    # print(f"🔍  Map coordinates: {estimated_lat:.6f}, {estimated_lng:.6f}")
    
    # Create temporary directory for map files
    temp_dir = tempfile.mkdtemp(prefix='realagent_map_')
    map_file = os.path.join(temp_dir, 'address_correction_map.html')
    
    try:
        # Create the interactive map
        m = folium.Map(
            location=[estimated_lat, estimated_lng],
            zoom_start=13,
            tiles='OpenStreetMap'
        )
        
        # Add a draggable green marker for the estimated location
        folium.Marker(
            [estimated_lat, estimated_lng],
            icon=folium.Icon(color='green', icon='home'),
            draggable=True
        ).add_to(m)
        
        # Create control panel HTML that will be injected
        control_panel_html = f"""
        <div class="control-panel">
            <h3>📍 Address Correction</h3>
            <div class="instructions">
                <strong>Original:</strong><br>
                <em>{original_address}</em>
            </div>
            
            <!-- Address Search Bar -->
            <div class="search-section">
                <div class="search-container">
                    <input type="text" id="address-search" placeholder="🔍 Search for street or address..." 
                           class="search-input" autocomplete="off">
                    <button id="search-btn" class="search-btn" onclick="searchAddress()">
                        <span class="search-icon">🔍</span>
                    </button>
                </div>
                <div id="search-results" class="search-results" style="display: none;"></div>
            </div>
            
            <div class="instructions">
                <strong>Instructions:</strong><br>
                • Search for address above, or<br>
                • Click anywhere on the map to move marker<br>
                • Or drag the marker to fine-tune position<br>
                • Tap "Confirm Location" when ready
            </div>
            <div id="selected-info" style="display: none;">
                <div class="address-info">
                    <strong>Selected Address:</strong><br>
                    <span id="selected-address">Loading...</span>
                </div>
                <div class="coordinates-info">
                    <strong>Coordinates:</strong><br>
                    <span id="selected-coords">0.000000, 0.000000</span>
                </div>
            </div>
            <button id="confirm-btn" class="confirm-btn" onclick="confirmSelection()" disabled>
                ✅ Confirm Location
            </button>
            <button class="cancel-btn" onclick="cancelSelection()">
                ❌ Cancel
            </button>
        </div>
        """
        
        # Add the control panel and JavaScript using Folium's HTML injection
        from folium import Element
        
        # Add CSS and HTML
        css_and_html = f"""
        <style>
        .control-panel {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 24px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15), 0 0 0 0.5px rgba(255,255,255,0.3);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            z-index: 1000;
            max-width: 320px;
            border: 1px solid rgba(255,255,255,0.2);
            transition: all 0.3s ease;
        }}
        .control-panel h3 {{
            margin: 0 0 20px 0;
            color: #1d1d1f;
            font-size: 20px;
            font-weight: 600;
            text-align: center;
        }}
        .address-info {{
            background: rgba(0, 122, 255, 0.1);
            padding: 16px;
            border-radius: 12px;
            margin: 12px 0;
            border: 1px solid rgba(0, 122, 255, 0.2);
        }}
        .coordinates-info {{
            background: rgba(52, 199, 89, 0.1);
            padding: 16px;
            border-radius: 12px;
            margin: 12px 0;
            border: 1px solid rgba(52, 199, 89, 0.2);
        }}
        .confirm-btn {{
            background: linear-gradient(135deg, #007AFF 0%, #0051D5 100%);
            color: white;
            border: none;
            padding: 16px 24px;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin-top: 16px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
        }}
        .confirm-btn:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(0, 122, 255, 0.4);
        }}
        .confirm-btn:active {{
            transform: translateY(0px);
            box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
        }}
        .confirm-btn:disabled {{
            background: #8E8E93;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }}
        .cancel-btn {{
            background: rgba(255, 59, 48, 0.1);
            color: #FF3B30;
            border: 1px solid rgba(255, 59, 48, 0.2);
            padding: 12px 20px;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            width: 100%;
            margin-top: 8px;
            transition: all 0.2s ease;
        }}
        .cancel-btn:hover {{
            background: rgba(255, 59, 48, 0.15);
            transform: translateY(-1px);
        }}
        .cancel-btn:active {{
            transform: translateY(0px);
        }}
        .instructions {{
            color: #6d6d70;
            font-size: 15px;
            line-height: 1.4;
            margin: 16px 0;
            text-align: left;
        }}
        .instructions strong {{
            color: #1d1d1f;
            font-weight: 600;
        }}
        .loading {{
            color: #007AFF;
            font-style: italic;
        }}
        
        /* Search Bar Styles */
        .search-section {{
            margin: 16px 0;
            padding: 16px 0;
            border-top: 1px solid rgba(0,0,0,0.1);
            border-bottom: 1px solid rgba(0,0,0,0.1);
        }}
        
        .search-container {{
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
        }}
        
        .search-input {{
            flex: 1;
            padding: 12px 16px;
            border: 2px solid rgba(0, 122, 255, 0.2);
            border-radius: 12px;
            font-size: 16px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: rgba(255, 255, 255, 0.9);
            transition: all 0.2s ease;
            outline: none;
        }}
        
        .search-input:focus {{
            border-color: #007AFF;
            background: white;
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
        }}
        
        .search-btn {{
            padding: 12px 16px;
            background: linear-gradient(135deg, #007AFF 0%, #0051D5 100%);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 16px;
        }}
        
        .search-btn:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
        }}
        
        .search-btn:active {{
            transform: translateY(0px);
        }}
        
        .search-results {{
            max-height: 200px;
            overflow-y: auto;
            background: white;
            border-radius: 12px;
            border: 1px solid rgba(0, 122, 255, 0.2);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .search-result-item {{
            padding: 12px 16px;
            border-bottom: 1px solid rgba(0,0,0,0.05);
            cursor: pointer;
            transition: background-color 0.15s ease;
            font-size: 14px;
            line-height: 1.3;
        }}
        
        .search-result-item:hover {{
            background: rgba(0, 122, 255, 0.05);
        }}
        
        .search-result-item:last-child {{
            border-bottom: none;
        }}
        
        .search-result-main {{
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 2px;
        }}
        
        .search-result-details {{
            color: #6d6d70;
            font-size: 13px;
        }}
        
        .search-loading {{
            padding: 16px;
            text-align: center;
            color: #007AFF;
            font-style: italic;
        }}
        
        .search-no-results {{
            padding: 16px;
            text-align: center;
            color: #8E8E93;
            font-style: italic;
        }}
        
        /* iOS-style success animation */
        @keyframes successPulse {{
            0% {{
                transform: scale(1);
                box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
            }}
            50% {{
                transform: scale(1.05);
                box-shadow: 0 8px 24px rgba(52, 199, 89, 0.5);
                background: linear-gradient(135deg, #34C759 0%, #30D158 100%);
            }}
            100% {{
                transform: scale(1);
                box-shadow: 0 4px 12px rgba(52, 199, 89, 0.3);
                background: linear-gradient(135deg, #34C759 0%, #30D158 100%);
            }}
        }}
        
        .confirm-btn.success {{
            animation: successPulse 0.6s ease-out;
            background: linear-gradient(135deg, #34C759 0%, #30D158 100%);
        }}
        
        .confirm-btn.success::before {{
            content: '✓';
            font-size: 20px;
            margin-right: 8px;
        }}
        
        /* Success overlay styles */
        .success-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            opacity: 0;
            animation: overlayFadeIn 0.8s ease-out forwards;
        }}
        
        .success-card {{
            background: linear-gradient(145deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.9));
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            padding: 32px 28px;
            border-radius: 24px;
            box-shadow: 
                0 25px 80px rgba(0,0,0,0.25),
                0 0 0 1px rgba(255,255,255,0.4),
                inset 0 1px 0 rgba(255,255,255,0.6);
            text-align: center;
            max-width: 380px;
            width: 90%;
            opacity: 0;
            animation: cardFadeIn 0.6s ease-out 0.3s forwards;
        }}
        
        .success-title {{
            color: #34C759;
            font-size: 22px;
            font-weight: 700;
            margin: 0 0 18px 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            letter-spacing: -0.5px;
        }}
        
        .success-address {{
            background: linear-gradient(135deg, rgba(52, 199, 89, 0.08), rgba(52, 199, 89, 0.12));
            padding: 18px 20px;
            border-radius: 16px;
            margin: 16px 0 0 0;
            border: 1px solid rgba(52, 199, 89, 0.15);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.3);
        }}
        
        .success-address h4 {{
            margin: 0 0 8px 0;
            color: #1d1d1f;
            font-size: 15px;
            font-weight: 600;
            opacity: 0.8;
        }}
        
        .success-address p {{
            margin: 0;
            color: #2d2d2d;
            font-size: 16px;
            line-height: 1.3;
            font-weight: 500;
        }}
        
        @keyframes overlayFadeIn {{
            to {{
                opacity: 1;
            }}
        }}
        
        @keyframes cardFadeIn {{
            to {{
                opacity: 1;
            }}
        }}
        </style>
        {control_panel_html}
        """
        
        # Add JavaScript that will run after the map is loaded
        javascript_code = f"""
        <script>
        // Wait for map to be fully loaded
        document.addEventListener('DOMContentLoaded', function() {{
            // Give the map a moment to initialize
            setTimeout(function() {{
                console.log('Initializing interactive map features...');
                
                var existingMarker = null;
                var currentLat = {estimated_lat};
                var currentLng = {estimated_lng};
                var currentAddress = null;
                
                // Get the map object (Folium creates it as 'map_' + random_id, but we can access it globally)
                var mapObj = window[Object.keys(window).find(key => key.startsWith('map_'))];
                if (!mapObj) {{
                    console.error('Could not find map object');
                    return;
                }}
                
                // Add map click handler to move marker
                function onMapClick(e) {{
                    console.log('Map clicked at:', e.latlng);
                    var lat = e.latlng.lat;
                    var lng = e.latlng.lng;
                    
                    // Move existing marker to clicked location
                    if (existingMarker) {{
                        existingMarker.setLatLng([lat, lng]);
                        console.log('Moved marker to clicked location');
                        updateLocationInfo(lat, lng);
                    }}
                }}
                
                // Add click event to map
                mapObj.on('click', onMapClick);
                console.log('Map click handler added');
                
                // Find the existing green marker and make it interactive
                setTimeout(function() {{
                    mapObj.eachLayer(function(layer) {{
                        if (layer instanceof L.Marker) {{
                            existingMarker = layer;
                            console.log('Found existing marker, making it interactive');
                            
                            // Add drag event listener to existing marker
                            existingMarker.on('dragend', function(e) {{
                                var marker = e.target;
                                var position = marker.getLatLng();
                                console.log('Green marker dragged to:', position);
                                updateLocationInfo(position.lat, position.lng);
                            }});
                            
                            // Also handle click on the marker to activate it
                            existingMarker.on('click', function(e) {{
                                console.log('Marker clicked, activating location info');
                                var position = e.target.getLatLng();
                                updateLocationInfo(position.lat, position.lng);
                                // Prevent map click event from firing
                                L.DomEvent.stopPropagation(e);
                            }});
                        }}
                    }});
                }}, 500); // Wait for marker to be fully rendered
                
                function updateLocationInfo(lat, lng) {{
                    currentLat = lat;
                    currentLng = lng;
                    
                    console.log('Updating location info:', lat, lng);
                    
                    // Update coordinates display
                    var coordsElement = document.getElementById('selected-coords');
                    if (coordsElement) {{
                        coordsElement.textContent = lat.toFixed(6) + ', ' + lng.toFixed(6);
                    }}
                    
                    // Show loading state
                    var addressElement = document.getElementById('selected-address');
                    var infoElement = document.getElementById('selected-info');
                    var confirmBtn = document.getElementById('confirm-btn');
                    
                    if (addressElement) {{
                        addressElement.innerHTML = '<span class="loading">Loading address...</span>';
                    }}
                    if (infoElement) {{
                        infoElement.style.display = 'block';
                    }}
                    if (confirmBtn) {{
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = '⏳ Loading Address...';
                    }}
                    
                    // Reverse geocode to get address
                    fetch('https://nominatim.openstreetmap.org/reverse?format=json&lat=' + lat + '&lon=' + lng + '&zoom=18&addressdetails=1')
                        .then(response => response.json())
                        .then(data => {{
                            currentAddress = data.display_name || (lat.toFixed(6) + ', ' + lng.toFixed(6));
                            if (addressElement) {{
                                addressElement.textContent = currentAddress;
                            }}
                            if (confirmBtn) {{
                                confirmBtn.textContent = '✅ Confirm Location';
                            }}
                            console.log('Address loaded:', currentAddress);
                        }})
                        .catch(error => {{
                            console.error('Geocoding error:', error);
                            currentAddress = lat.toFixed(6) + ', ' + lng.toFixed(6);
                            if (addressElement) {{
                                addressElement.textContent = 'Address lookup failed - using coordinates';
                            }}
                            if (confirmBtn) {{
                                confirmBtn.textContent = '✅ Confirm Location';
                            }}
                        }});
                }}
                
                
                // Global functions for buttons
                window.confirmSelection = function() {{
                    if (!currentLat || !currentLng) {{
                        alert('Please select a location on the map first.');
                        return;
                    }}
                    
                    console.log('Confirming selection:', currentLat, currentLng, currentAddress);
                    
                    // Add success animation to button
                    var confirmBtn = document.getElementById('confirm-btn');
                    if (confirmBtn) {{
                        confirmBtn.disabled = true;
                        confirmBtn.textContent = '⏳ Confirming...';
                        
                        // Add success animation after a short delay
                        setTimeout(function() {{
                            confirmBtn.classList.add('success');
                            confirmBtn.textContent = 'Location Confirmed!';
                        }}, 800);
                    }}
                    
                    // Send coordinates to server
                    fetch('/select_coordinates', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            lat: currentLat,
                            lng: currentLng,
                            address: currentAddress || (currentLat.toFixed(6) + ', ' + currentLng.toFixed(6))
                        }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            // Show success overlay after animation completes
                            setTimeout(function() {{
                                // Create overlay element
                                var overlay = document.createElement('div');
                                overlay.className = 'success-overlay';
                                overlay.innerHTML = `
                                    <div class="success-card">
                                        <h2 class="success-title">✅ Location Confirmed</h2>
                                        <div class="success-address">
                                            <h4>Selected Address:</h4>
                                            <p>${{currentAddress}}</p>
                                        </div>
                                    </div>
                                `;
                                document.body.appendChild(overlay);
                                
                                // Auto-close tab after 3 seconds (reduced from 8 seconds)
                                setTimeout(function() {{
                                    window.close();
                                }}, 3000);
                            }}, 1200); // Wait for animation to complete
                        }} else {{
                            alert('Error confirming selection. Please try again.');
                            if (confirmBtn) {{
                                confirmBtn.disabled = false;
                                confirmBtn.textContent = '✅ Confirm Location';
                            }}
                        }}
                    }})
                    .catch(error => {{
                        console.error('Error:', error);
                        alert('Network error. Please check your connection and try again.');
                        if (confirmBtn) {{
                            confirmBtn.disabled = false;
                            confirmBtn.textContent = '✅ Confirm Location';
                        }}
                    }});
                }};
                
                window.cancelSelection = function() {{
                    if (confirm('Are you sure you want to cancel? This will return you to the manual address input.')) {{
                        window.close();
                        // If window.close() doesn't work (some browsers block it), show message
                        setTimeout(function() {{
                            document.body.innerHTML = `
                                <div style="text-align: center; margin-top: 100px; font-family: Arial, sans-serif; padding: 40px;">
                                    <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;">
                                        <h1 style="color: #dc3545; margin-bottom: 20px;">❌ Selection Cancelled</h1>
                                        <p style="font-size: 18px; color: #666;">
                                            Please close this browser tab and return to the terminal to choose a different option.
                                        </p>
                                    </div>
                                </div>
                            `;
                        }}, 100);
                    }}
                }};
                
                // Romanian diacritics normalization
                function normalizeDiacritics(text) {{
                    var diacriticsMap = {{
                        'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
                        'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T'
                    }};
                    return text.replace(/[ăâîșțĂÂÎȘȚ]/g, function(match) {{
                        return diacriticsMap[match] || match;
                    }});
                }}
                
                // Extract street name from full address
                function extractStreetName(displayName) {{
                    if (!displayName) return '';
                    
                    // Get the first part (before first comma)
                    var firstPart = displayName.split(',')[0].trim();
                    
                    // Remove common prefixes to get just the street name
                    var streetName = firstPart
                        .replace(/^(strada|str\\.?|bulevardul|bd\\.?|piața|aleea)\\s+/i, '')
                        .replace(/\\s+(street|lane|boulevard|square)$/i, '')
                        .trim();
                    
                    return streetName;
                }}
                
                // Address Search Functionality
                window.searchAddress = function() {{
                    var searchInput = document.getElementById('address-search');
                    var searchResults = document.getElementById('search-results');
                    var query = searchInput.value.trim();
                    
                    if (!query) {{
                        searchResults.style.display = 'none';
                        return;
                    }}
                    
                    // Show loading state
                    searchResults.style.display = 'block';
                    searchResults.innerHTML = '<div class="search-loading">🔍 Searching addresses...</div>';
                    
                    // Create multiple search queries to handle diacritics
                    var searchQueries = [
                        query, // Original query
                        normalizeDiacritics(query) // Query without diacritics
                    ];
                    
                    // Add common Romanian street prefixes if not present
                    var commonPrefixes = ['strada', 'str.', 'bulevardul', 'bd.', 'piața'];
                    var hasPrefix = commonPrefixes.some(prefix => 
                        query.toLowerCase().startsWith(prefix.toLowerCase())
                    );
                    
                    if (!hasPrefix && query.length > 2) {{
                        searchQueries.push('strada ' + query);
                        searchQueries.push('str. ' + query);
                        searchQueries.push('strada ' + normalizeDiacritics(query));
                        searchQueries.push('str. ' + normalizeDiacritics(query));
                    }}
                    
                    // Remove duplicates
                    searchQueries = [...new Set(searchQueries)];
                    
                    console.log('Search queries:', searchQueries);
                    
                    // Function to search with multiple queries
                    var allResults = [];
                    var completedSearches = 0;
                    
                    searchQueries.forEach(function(searchQuery) {{
                        var searchUrl = 'https://nominatim.openstreetmap.org/search?format=json&limit=5&countrycodes=md&addressdetails=1&q=' + encodeURIComponent(searchQuery + ', Moldova');
                        
                        fetch(searchUrl)
                            .then(response => response.json())
                            .then(data => {{
                                if (data && data.length > 0) {{
                                    // Add results with source query info
                                    data.forEach(function(result) {{
                                        result.searchQuery = searchQuery;
                                        allResults.push(result);
                                    }});
                                }}
                                
                                completedSearches++;
                                
                                // When all searches are complete, process results
                                if (completedSearches === searchQueries.length) {{
                                    processSearchResults(allResults, searchResults);
                                }}
                            }})
                            .catch(error => {{
                                console.error('Search error for query "' + searchQuery + '":', error);
                                completedSearches++;
                                
                                if (completedSearches === searchQueries.length) {{
                                    processSearchResults(allResults, searchResults);
                                }}
                            }});
                    }});
                }};
                
                // Process and display search results
                function processSearchResults(allResults, searchResults) {{
                    if (allResults.length > 0) {{
                        // Remove duplicates based on street name similarity and location
                        var uniqueResults = [];
                        allResults.forEach(function(result) {{
                            var resultStreetName = extractStreetName(result.display_name);
                            
                            var isDuplicate = uniqueResults.some(function(existing) {{
                                var existingStreetName = extractStreetName(existing.display_name);
                                
                                // Check if street names are similar (normalized)
                                var normalizedResult = normalizeDiacritics(resultStreetName.toLowerCase());
                                var normalizedExisting = normalizeDiacritics(existingStreetName.toLowerCase());
                                
                                // Consider duplicate if:
                                // 1. Same street name (after normalization)
                                // 2. OR within 200m distance
                                var isSameStreet = normalizedResult === normalizedExisting;
                                
                                var distance = Math.sqrt(
                                    Math.pow((parseFloat(result.lat) - parseFloat(existing.lat)) * 111000, 2) +
                                    Math.pow((parseFloat(result.lon) - parseFloat(existing.lon)) * 111000, 2)
                                );
                                var isNearby = distance < 200; // 200 meters threshold
                                
                                return isSameStreet || (isNearby && resultStreetName.length > 0 && existingStreetName.length > 0);
                            }});
                            
                            if (!isDuplicate) {{
                                uniqueResults.push(result);
                            }}
                        }});
                        
                        // Sort by relevance (prefer results with street prefixes, then by importance)
                        uniqueResults.sort(function(a, b) {{
                            var aHasStreet = /\\b(strada|str\\.|bulevardul|bd\\.|piața)/i.test(a.display_name);
                            var bHasStreet = /\\b(strada|str\\.|bulevardul|bd\\.|piața)/i.test(b.display_name);
                            
                            if (aHasStreet && !bHasStreet) return -1;
                            if (!aHasStreet && bHasStreet) return 1;
                            
                            // If both are streets, prefer the one with higher importance
                            var aImportance = parseFloat(a.importance || 0);
                            var bImportance = parseFloat(b.importance || 0);
                            return bImportance - aImportance;
                        }});
                        
                        // Limit to top 6 results to avoid clutter
                        uniqueResults = uniqueResults.slice(0, 6);
                        
                        var resultsHtml = '';
                        uniqueResults.forEach(function(result) {{
                            var mainText = result.display_name.split(',')[0];
                            var detailText = result.display_name.split(',').slice(1, 3).join(',').trim();
                            
                            // Highlight matching parts (simple highlighting)
                            var searchInput = document.getElementById('address-search');
                            var originalQuery = searchInput.value.trim().toLowerCase();
                            var normalizedQuery = normalizeDiacritics(originalQuery);
                            
                            if (originalQuery.length > 2) {{
                                var regex = new RegExp('(' + originalQuery.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                                mainText = mainText.replace(regex, '<strong>$1</strong>');
                                
                                if (originalQuery !== normalizedQuery) {{
                                    var normalizedRegex = new RegExp('(' + normalizedQuery.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                                    mainText = mainText.replace(normalizedRegex, '<strong>$1</strong>');
                                }}
                            }}
                            
                            resultsHtml += `
                                <div class="search-result-item" onclick="selectSearchResult(${{result.lat}}, ${{result.lon}}, '${{result.display_name.replace(/'/g, "\\'")}}')" 
                                     data-lat="${{result.lat}}" data-lon="${{result.lon}}" data-address="${{result.display_name}}">
                                    <div class="search-result-main">${{mainText}}</div>
                                    <div class="search-result-details">${{detailText}}</div>
                                </div>
                            `;
                        }});
                        searchResults.innerHTML = resultsHtml;
                    }} else {{
                        searchResults.innerHTML = '<div class="search-no-results">No addresses found. Try a different search term or check spelling.</div>';
                    }}
                }}
                
                // Select search result
                window.selectSearchResult = function(lat, lon, address) {{
                    console.log('Selected search result:', lat, lon, address);
                    
                    // Move marker to selected location
                    if (existingMarker) {{
                        existingMarker.setLatLng([lat, lon]);
                        mapObj.setView([lat, lon], 16); // Zoom to location
                    }}
                    
                    // Update location info
                    updateLocationInfo(lat, lon);
                    
                    // Hide search results
                    var searchResults = document.getElementById('search-results');
                    searchResults.style.display = 'none';
                    
                    // Clear search input
                    var searchInput = document.getElementById('address-search');
                    searchInput.value = '';
                    
                    // Set address directly from search result
                    currentAddress = address;
                    var addressElement = document.getElementById('selected-address');
                    if (addressElement) {{
                        addressElement.textContent = address;
                    }}
                }};
                
                // Add Enter key support for search
                setTimeout(function() {{
                    var searchInput = document.getElementById('address-search');
                    if (searchInput) {{
                        searchInput.addEventListener('keypress', function(e) {{
                            if (e.key === 'Enter') {{
                                searchAddress();
                            }}
                        }});
                        
                        // Auto-search as user types (with debounce)
                        var searchTimeout;
                        searchInput.addEventListener('input', function() {{
                            clearTimeout(searchTimeout);
                            searchTimeout = setTimeout(function() {{
                                if (searchInput.value.trim().length >= 3) {{
                                    searchAddress();
                                }} else {{
                                    document.getElementById('search-results').style.display = 'none';
                                }}
                            }}, 500);
                        }});
                        
                        // Hide results when clicking outside
                        document.addEventListener('click', function(e) {{
                            if (!e.target.closest('.search-section')) {{
                                document.getElementById('search-results').style.display = 'none';
                            }}
                        }});
                    }}
                }}, 1500);
                
                
            }}, 1000); // Wait 1 second for map to fully initialize
        }});
        </script>
        """
        
        # Add the HTML and JavaScript to the map
        m.get_root().html.add_child(Element(css_and_html + javascript_code))
        
        # Save the map
        m.save(map_file)
        
        # Start local server
        server = MapOverlayServer()
        server_url = server.start_server(temp_dir)
        
        # Open map in browser (Safari for macOS, Edge for Windows)
        map_url = f"{server_url}/address_correction_map.html"
        import platform
        import subprocess
        
        try:
            if platform.system() == 'Darwin':  # macOS
                # Open in Safari
                subprocess.Popen(['open', '-a', 'Safari', map_url])
            elif platform.system() == 'Windows':
                # Open in Edge
                subprocess.Popen(['start', 'msedge', map_url], shell=True)
            else:  # Linux
                webbrowser.open(map_url)
        except Exception:
            # Final fallback to default browser
            webbrowser.open(map_url)
        
        print("⏳  Please select the correct location on the map...")
        
        # Wait for user selection (with timeout)
        timeout = 300  # 5 minutes timeout
        start_time = time.time()
        
        while server.selected_coordinates is None:
            if time.time() - start_time > timeout:
                print("\n⏰  Timeout reached. Cancelling map selection...")
                break
            time.sleep(0.5)
        
        # Stop server immediately after receiving coordinates (don't wait for browser to close)
        server.stop_server()
        
        if server.selected_coordinates:
            print("✅  Location confirmed!")
            lat, lng = server.selected_coordinates
            address = server.selected_address
            
            # Parse address components for table display
            import re
            
            # Try to extract street, district, and building from the address
            street = ""
            district = ""
            building = ""
            
            # Simple parsing - can be enhanced based on address format
            if address:
                # Look for building number (digits at the end or after street name)
                building_match = re.search(r'\b(\d+[a-zA-Z]?)\b', address)
                if building_match:
                    building = building_match.group(1)
                
                # Look for district/sector (common patterns)
                district_patterns = [
                    r'\b(Botanica|Centru|Ciocana|Râșcani|Buiucani)\b',
                    r'\b(Sector \d+)\b',
                    r'\b([A-Z][a-z]+)\s+(?:District|Sector)\b'
                ]
                for pattern in district_patterns:
                    district_match = re.search(pattern, address, re.IGNORECASE)
                    if district_match:
                        district = district_match.group(1)
                        break
                
                # Extract street (everything before building number or comma)
                street_part = address.split(',')[0] if ',' in address else address
                if building:
                    street_part = street_part.replace(building, '').strip()
                street = street_part.strip()
            
            # print(f"\n✅  Location selected: {address}")
            # print(f"📍  Coordinates: {lat:.6f}, {lng:.6f}")
            
            # Format the address before returning
            try:
                from Helper.address_formatter import format_address_for_display
                formatted_addresses = format_address_for_display(address)
                # Return the Romanian formatted address as the main address
                formatted_address = formatted_addresses.get('ro', address)
                return lat, lng, formatted_address
            except Exception as e:
                print(f"Warning: Address formatting failed: {e}")
                return lat, lng, address
        else:
            print("\n❌  No location selected or operation cancelled.")
            return None
            
    except Exception as e:
        print(f"\n❌  Error creating interactive map: {e}")
        return None
    
    finally:
        # Cleanup temporary files
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

def test_map_overlay():
    """Test function for the map overlay."""
    print("🧪  Testing map overlay...")
    result = create_interactive_map("Test Address, Chișinău")
    if result:
        lat, lng, address = result
        print(f"✅  Test successful: {lat}, {lng} - {address}")
    else:
        print("❌  Test failed or cancelled")

if __name__ == "__main__":
    test_map_overlay()
