#!/usr/bin/env python3
"""
RealAgent Simple Dashboard
==========================

A lightweight Flask-based dashboard to view all listings from Mainframe.db.
This dashboard displays all properties in a card grid with thumbnails and
provides direct links to view the full listing HTML.

Usage:
    python dashboard_simple.py

Then open: http://localhost:5000

Dependencies:
    - Flask (install: pip install flask)
    - sqlite3 (included in Python standard library)
"""

from flask import Flask, render_template, send_from_directory, abort, jsonify, request, Response
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from collections import Counter
import sys
import io
import base64

# QR Code imports
import qrcode
import segno

# Add Helper to path for database functions
sys.path.insert(0, str(Path(__file__).parent))
from Helper.database import (
    add_journal_entry,
    get_journal_entries,
    update_journal_entry,
    delete_journal_entry,
    update_listing_fields,
    update_image_order,
    get_listing_from_mainframe
)
from Helper.db_metrics import timed_db_connection, db_metrics, with_db_metrics
from regenerate_html import regenerate_listing_by_id

app = Flask(__name__, 
            template_folder='Templates/Dashboard',
            static_folder='Templates/Dashboard',
            static_url_path='')

# Disable caching for development
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Add cache control headers to all responses
@app.after_request
def add_cache_control_headers(response):
    """Add headers to prevent caching of dynamic content, but allow caching for images."""
    # Allow caching for images (webp, jpg, jpeg, png, gif)
    content_type = response.headers.get('Content-Type', '')
    if content_type.startswith('image/'):
        # Cache images for 1 hour in browser, 1 day in shared caches
        response.headers['Cache-Control'] = 'public, max-age=3600, s-maxage=86400'
        return response
    
    # No caching for dynamic content (HTML, JSON, etc.)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Configuration
DB_PATH = Path(__file__).parent / "Mainframe.db"
LISTINGS_DIR = Path(__file__).parent / "Listings"


def generate_qr_code(listing_data, format='svg'):
    """Generate QR code in requested format (svg or png)"""
    
    # Get local network IP for smartphone access
    import socket
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        # Fallback to localhost if can't determine IP
        local_ip = "localhost"
    
    # Get the actual port from Flask request context or use default
    try:
        from flask import request
        port = request.host.split(':')[1] if ':' in request.host else '5000'
    except:
        port = '5000'
    
    # Create listing URL for local network access
    listing_url = f"http://{local_ip}:{port}/listings/{listing_data['id']}/index.html"
    
    if format == 'svg':
        try:
            # Vector format using segno
            qr = segno.make(listing_url)
            
            buffer = io.BytesIO()
            qr.save(buffer, 
                   scale=8, 
                   light="#ffffff", 
                   dark="#000000",  # Black QR code pattern
                   kind='svg')
            
            svg_bytes = buffer.getvalue()
            svg_content = svg_bytes.decode('utf-8')
            
            return svg_content
            
        except Exception as e:
            print(f"SVG generation error: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise
    
    elif format == 'png':
        try:
            # Raster format using qrcode + PIL
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(listing_url)
            qr.make(fit=True)
            
            # Create image with black QR code pattern
            img = qr.make_image(fill_color="#000000", back_color="white")
            
            # Convert to base64 for web display
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            
            img_str = base64.b64encode(img_bytes).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            print(f"PNG generation error: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise
    
    else:
        raise ValueError(f"Unsupported format: {format}")


def get_db_connection(endpoint="unknown"):
    """Create a database connection with row factory for dict-like access and performance metrics."""
    conn = timed_db_connection(DB_PATH, endpoint)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_statistics():
    """
    Calculate comprehensive statistics from all listings.
    Enhanced with deep analytics for rent vs sale comparison.
    
    Returns:
        Dictionary containing statistics data
    """
    try:
        conn = get_db_connection("statistics")
        cursor = conn.cursor()
        
        # Total listings count
        cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'active'")
        total_listings = cursor.fetchone()[0]
        
        # Count by listing type and status
        cursor.execute("""
            SELECT 
                listing_type,
                sold,
                rented,
                COUNT(*) as count
            FROM listings 
            WHERE status = 'active'
            GROUP BY listing_type, sold, rented
        """)
        type_status_rows = cursor.fetchall()
        
        # Initialize counters
        for_sale_available = 0
        for_sale_sold = 0
        for_rent_available = 0
        for_rent_rented = 0
        
        for row in type_status_rows:
            listing_type = row[0] if row[0] else 'for_sale'  # Default to for_sale
            sold = row[1] if row[1] else 'no'
            rented = row[2] if row[2] else 'no'
            count = row[3]
            
            if listing_type == 'for_sale':
                if sold == 'yes':
                    for_sale_sold += count
                else:
                    for_sale_available += count
            elif listing_type == 'for_rent':
                if rented == 'yes':
                    for_rent_rented += count
                else:
                    for_rent_available += count
        
        # Query to get listing features for rooms and surface
        cursor.execute("""
            SELECT l.id, l.listing_type, f.feature_key, f.feature_value
            FROM listings l
            LEFT JOIN listing_features f ON l.id = f.listing_id
            WHERE l.status = 'active'
        """)
        
        rooms_distribution_sale = Counter()
        rooms_distribution_rent = Counter()
        surface_areas_sale = {'house': [], 'apartment': [], 'commercial': []}
        surface_areas_rent = {'house': [], 'apartment': [], 'commercial': []}
        sale_prices_by_type = {'house': [], 'apartment': [], 'commercial': []}
        rent_prices_by_type = {'house': [], 'apartment': [], 'commercial': []}
        
        # Organize data by listing
        listing_features_map = {}
        for row in cursor.fetchall():
            listing_id, listing_type, feature_key, feature_value = row
            
            if listing_id not in listing_features_map:
                listing_features_map[listing_id] = {'type': listing_type, 'features': {}}
            
            if feature_key and feature_value:
                listing_features_map[listing_id]['features'][feature_key.lower()] = feature_value.lower()
        
        # Now process prices after we have the listing_features_map
        # Get all prices for calculations
        cursor.execute("SELECT id, price_json, listing_type, sold, rented FROM listings WHERE status = 'active'")
        price_rows = cursor.fetchall()
        
        prices = []
        sale_prices = []
        rent_prices = []
        total_value = 0
        currencies = Counter()
        
        # Create a mapping of listing ID to property type (direct from database)
        listing_property_types = {}
        for listing_id, features_data in listing_features_map.items():
            # Use property type directly from listings table
            property_type = features_data.get('property_type', 'apartment')
            property_type_clean = property_type.lower() if property_type else 'apartment'
            listing_property_types[listing_id] = property_type_clean
        
        for row in price_rows:
            listing_id, price_json_str, listing_type, sold, rented = row
            if price_json_str:
                try:
                    price_obj = json.loads(price_json_str)
                    listing_type = listing_type if listing_type else 'for_sale'
                    property_type = listing_property_types.get(listing_id, 'apartment')
                    
                    for currency, price_str in price_obj.items():
                        # Extract numeric value from price string
                        numeric_price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_str.replace(',', '').replace(' ', '')))
                        if numeric_price:
                            price_val = float(numeric_price)
                            prices.append(price_val)
                            total_value += price_val
                            currencies[currency] += 1
                            
                            # Separate by listing type and property type
                            if listing_type == 'for_sale':
                                sale_prices.append(price_val)
                                sale_prices_by_type[property_type].append(price_val)
                            elif listing_type == 'for_rent':
                                rent_prices.append(price_val)
                                rent_prices_by_type[property_type].append(price_val)
                except (json.JSONDecodeError, ValueError):
                    pass
        
        # Calculate overall price statistics
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        # Calculate sale-specific price statistics
        sale_avg_price = sum(sale_prices) / len(sale_prices) if sale_prices else 0
        sale_min_price = min(sale_prices) if sale_prices else 0
        sale_max_price = max(sale_prices) if sale_prices else 0
        
        # Calculate rent-specific price statistics
        rent_avg_price = sum(rent_prices) / len(rent_prices) if rent_prices else 0
        rent_min_price = min(rent_prices) if rent_prices else 0
        rent_max_price = max(rent_prices) if rent_prices else 0
        
        # Most common currency
        most_common_currency = currencies.most_common(1)[0][0] if currencies else 'EUR'
        
        # Location statistics - extract detailed location info
        cursor.execute("""
            SELECT id, address FROM listings 
            WHERE status = 'active' AND address IS NOT NULL AND address != ''
        """)
        addresses = cursor.fetchall()
        
        # Parse addresses to extract meaningful location data
        # Format: "City mun., City, District, str. Street, Number"
        locations = []
        for addr_row in addresses:
            listing_id = addr_row[0]
            full_address = addr_row[1]
            
            if full_address:
                parts = [p.strip() for p in full_address.split(',')]
                
                # Try to extract: City, District, Street
                city = None
                district = None
                street = None
                
                if len(parts) >= 2:
                    # First part usually has "mun." - get city from it or second part
                    if 'mun.' in parts[0]:
                        city = parts[0].replace('mun.', '').strip()
                    elif len(parts) > 1:
                        city = parts[1].strip()
                    
                    # Look for district in any part
                    for part in parts:
                        if any(d in part.lower() for d in ['raion', 'raionul', 'sector']):
                            district = part.strip()
                            break
                    
                    # Look for street in any part
                    for part in parts:
                        if any(s in part.lower() for s in ['str.', 'strada', 'bd.', 'bulevardul']):
                            street = part.strip()
                            break
                
                if city or district or street:
                    # Create a label for the location
                    location_parts = []
                    if city:
                        location_parts.append(city)
                    if district:
                        location_parts.append(district)
                    if street:
                        location_parts.append(street)
                    location_label = ', '.join(location_parts)
                    
                    locations.append({
                        'listing_id': listing_id,
                        'label': location_label,
                        'city': city,
                        'district': district,
                        'street': street,
                        'full_address': full_address
                    })
        
        # Count locations by full label (city + district + street)
        location_labels = [loc['label'] for loc in locations]
        location_counts = Counter(location_labels).most_common(10)
        
        # Date range
        cursor.execute("""
            SELECT MIN(created_at), MAX(created_at) 
            FROM listings WHERE status = 'active'
        """)
        date_range = cursor.fetchone()
        oldest_date = date_range[0] if date_range[0] else None
        newest_date = date_range[1] if date_range[1] else None
        
        # Image statistics
        cursor.execute("""
            SELECT COUNT(*) FROM listing_images li
            JOIN listings l ON li.listing_id = l.id
            WHERE l.status = 'active'
        """)
        total_images = cursor.fetchone()[0]
        avg_images = total_images / total_listings if total_listings > 0 else 0
        
        # Listings by creation date (last 7 entries)
        cursor.execute("""
            SELECT id, title_ro, created_at
            FROM listings 
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 7
        """)
        recent_listings = []
        for row in cursor.fetchall():
            recent_listings.append({
                'id': row[0],
                'title': row[1][:50] + '...' if row[1] and len(row[1]) > 50 else row[1],
                'date': row[2]
            })
        
        # ========== ENHANCED ANALYTICS ==========
        
        # 1. PROPERTY TYPES FROM DATABASE & ROOMS FROM FEATURES
        # Query to get property types directly from listings table
        cursor.execute("""
            SELECT listing_type, property_type
            FROM listings
            WHERE status = 'active'
        """)
        
        property_types_sale = Counter()
        property_types_rent = Counter()
        
        for row in cursor.fetchall():
            listing_type, property_type = row
            prop_type = property_type or 'apartment'  # Default to apartment if null
            
            if listing_type == 'for_sale':
                property_types_sale[prop_type] += 1
            elif listing_type == 'for_rent':
                property_types_rent[prop_type] += 1
        
        # Query to get listing features for rooms and surface, plus property type from listings
        cursor.execute("""
            SELECT l.id, l.listing_type, l.property_type, f.feature_key, f.feature_value
            FROM listings l
            LEFT JOIN listing_features f ON l.id = f.listing_id
            WHERE l.status = 'active'
        """)
        
        rooms_distribution_sale = Counter()
        rooms_distribution_rent = Counter()
        surface_areas_sale = {'house': [], 'apartment': [], 'commercial': []}
        surface_areas_rent = {'house': [], 'apartment': [], 'commercial': []}
        sale_prices_by_type = {'house': [], 'apartment': [], 'commercial': []}
        rent_prices_by_type = {'house': [], 'apartment': [], 'commercial': []}
        
        # Organize data by listing
        listing_features_map = {}
        all_feature_keys = set()
        
        for row in cursor.fetchall():
            listing_id, listing_type, property_type, feature_key, feature_value = row
            
            if listing_id not in listing_features_map:
                listing_features_map[listing_id] = {
                    'type': listing_type, 
                    'property_type': property_type,  # Direct from listings table
                    'features': {}
                }
            
            if feature_key and feature_value:
                listing_features_map[listing_id]['features'][feature_key.lower()] = feature_value.lower()
                all_feature_keys.add(feature_key.lower())
        
        # Analyze each listing's features
        debug_counts = {'total': 0, 'with_surface': 0, 'with_property_type': 0, 'house': 0, 'apartment': 0, 'commercial': 0}
        
        for listing_id, data in listing_features_map.items():
            listing_type = data['type']
            features = data['features']
            property_type = data['property_type']  # Direct from listings table
            debug_counts['total'] += 1
            
            # Count property types from database
            if property_type:
                debug_counts['with_property_type'] += 1
                if property_type.lower() == 'house':
                    debug_counts['house'] += 1
                elif property_type.lower() == 'commercial':
                    debug_counts['commercial'] += 1
                elif property_type.lower() == 'apartment':
                    debug_counts['apartment'] += 1
            
            # Extract rooms
            rooms = None
            for key in ['număr de camere', 'camere', 'nr. camere']:
                if key in features:
                    try:
                        rooms = int(features[key].split()[0])
                        break
                    except (ValueError, IndexError):
                        pass
            
            if rooms:
                if listing_type == 'for_sale':
                    rooms_distribution_sale[rooms] += 1
                elif listing_type == 'for_rent':
                    rooms_distribution_rent[rooms] += 1
            
            # Extract surface area
            surface = None
            for key in ['suprafața totală', 'suprafața totală', 'suprafață locativă', 'общая площадь', 'жилая площадь']:
                if key in features:
                    try:
                        surface_str = features[key].replace('m²', '').replace('m2', '').strip()
                        surface = float(surface_str.split()[0])
                        debug_counts['with_surface'] += 1
                        break
                    except (ValueError, IndexError):
                        pass
            
            # Use property type directly from database
            if property_type:
                property_type_clean = property_type.lower()
            else:
                property_type_clean = 'apartment'  # fallback
            
            if surface:
                if listing_type == 'for_sale':
                    surface_areas_sale[property_type_clean].append(surface)
                elif listing_type == 'for_rent':
                    surface_areas_rent[property_type_clean].append(surface)
        
        # 2. PRICE PERCENTILES
        def calculate_percentiles(price_list):
            if not price_list:
                return {'p25': 0, 'p50': 0, 'p75': 0, 'p90': 0}
            sorted_prices = sorted(price_list)
            n = len(sorted_prices)
            return {
                'p25': sorted_prices[int(n * 0.25)] if n > 0 else 0,
                'p50': sorted_prices[int(n * 0.50)] if n > 0 else 0,
                'p75': sorted_prices[int(n * 0.75)] if n > 0 else 0,
                'p90': sorted_prices[int(n * 0.90)] if n > 0 else 0
            }
        
        sale_percentiles = calculate_percentiles(sale_prices)
        rent_percentiles = calculate_percentiles(rent_prices)
        
        # 3. PRICE PER SQM ANALYSIS - Calculate per listing
        sale_price_per_sqm = {'house': [], 'apartment': [], 'commercial': []}
        rent_price_per_sqm = {'house': [], 'apartment': [], 'commercial': []}
        
        # Calculate price per m² for each listing individually
        for listing_id, data in listing_features_map.items():
            listing_type = data['type']
            property_type = data['property_type']
            features = data['features']
            
            if not property_type:
                property_type = 'apartment'
            property_type_clean = property_type.lower()
            
            # Get price for this listing
            cursor.execute("SELECT price_json FROM listings WHERE id = ? AND status = 'active'", (listing_id,))
            price_row = cursor.fetchone()
            
            if price_row and price_row[0]:
                try:
                    price_obj = json.loads(price_row[0])
                    # Extract surface area for this listing
                    surface = None
                    for key in ['suprafața totală', 'suprafața totală', 'suprafață locativă', 'общая площадь', 'жилая площадь']:
                        if key in features:
                            try:
                                surface_str = features[key].replace('m²', '').replace('m2', '').strip()
                                surface = float(surface_str.split()[0])
                                break
                            except (ValueError, IndexError):
                                pass
                    
                    if surface and surface > 0:
                        # Calculate price per m² for each currency
                        for currency, price_str in price_obj.items():
                            numeric_price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_str.replace(',', '').replace(' ', '')))
                            if numeric_price:
                                price_val = float(numeric_price)
                                price_per_sqm = price_val / surface
                                
                                if listing_type == 'for_sale':
                                    sale_price_per_sqm[property_type_clean].append(price_per_sqm)
                                elif listing_type == 'for_rent':
                                    rent_price_per_sqm[property_type_clean].append(price_per_sqm)
                except (json.JSONDecodeError, ValueError):
                    pass
        
        avg_price_per_sqm_sale = sum(sale_prices) / len(surface_areas_sale['apartment'] + surface_areas_sale['house'] + surface_areas_sale['commercial']) if (surface_areas_sale['apartment'] or surface_areas_sale['house'] or surface_areas_sale['commercial']) else 0
        avg_price_per_sqm_rent = sum(rent_prices) / len(surface_areas_rent['apartment'] + surface_areas_rent['house'] + surface_areas_rent['commercial']) if (surface_areas_rent['apartment'] or surface_areas_rent['house'] or surface_areas_rent['commercial']) else 0
        
        # 4. AMENITIES POPULARITY
        cursor.execute("""
            SELECT l.listing_type, la.amenity_key
            FROM listing_amenities la
            JOIN listings l ON la.listing_id = l.id
            WHERE l.status = 'active' AND la.lang = 'ro'
        """)
        
        amenities_sale = Counter()
        amenities_rent = Counter()
        
        for row in cursor.fetchall():
            listing_type = row[0] if row[0] else 'for_sale'
            amenity = row[1]
            
            if amenity:
                if listing_type == 'for_sale':
                    amenities_sale[amenity] += 1
                elif listing_type == 'for_rent':
                    amenities_rent[amenity] += 1
        
        
        # 6. SURFACE AREA STATISTICS
        avg_surface_sale = sum(surface_areas_sale['apartment'] + surface_areas_sale['house'] + surface_areas_sale['commercial']) / len(surface_areas_sale['apartment'] + surface_areas_sale['house'] + surface_areas_sale['commercial']) if (surface_areas_sale['apartment'] or surface_areas_sale['house'] or surface_areas_sale['commercial']) else 0
        avg_surface_rent = sum(surface_areas_rent['apartment'] + surface_areas_rent['house'] + surface_areas_rent['commercial']) / len(surface_areas_rent['apartment'] + surface_areas_rent['house'] + surface_areas_rent['commercial']) if (surface_areas_rent['apartment'] or surface_areas_rent['house'] or surface_areas_rent['commercial']) else 0
        
        # Calculate averages by property type
        avg_surface_sale_house = sum(surface_areas_sale['house']) / len(surface_areas_sale['house']) if surface_areas_sale['house'] else 0
        avg_surface_sale_apartment = sum(surface_areas_sale['apartment']) / len(surface_areas_sale['apartment']) if surface_areas_sale['apartment'] else 0
        avg_surface_sale_commercial = sum(surface_areas_sale['commercial']) / len(surface_areas_sale['commercial']) if surface_areas_sale['commercial'] else 0
        
        avg_surface_rent_house = sum(surface_areas_rent['house']) / len(surface_areas_rent['house']) if surface_areas_rent['house'] else 0
        avg_surface_rent_apartment = sum(surface_areas_rent['apartment']) / len(surface_areas_rent['apartment']) if surface_areas_rent['apartment'] else 0
        avg_surface_rent_commercial = sum(surface_areas_rent['commercial']) / len(surface_areas_rent['commercial']) if surface_areas_rent['commercial'] else 0
        
        # Calculate price per m² by property type
        avg_price_per_sqm_sale_house = sum(sale_price_per_sqm['house']) / len(sale_price_per_sqm['house']) if sale_price_per_sqm['house'] else 0
        avg_price_per_sqm_sale_apartment = sum(sale_price_per_sqm['apartment']) / len(sale_price_per_sqm['apartment']) if sale_price_per_sqm['apartment'] else 0
        avg_price_per_sqm_sale_commercial = sum(sale_price_per_sqm['commercial']) / len(sale_price_per_sqm['commercial']) if sale_price_per_sqm['commercial'] else 0
        
        avg_price_per_sqm_rent_house = sum(rent_price_per_sqm['house']) / len(rent_price_per_sqm['house']) if rent_price_per_sqm['house'] else 0
        avg_price_per_sqm_rent_apartment = sum(rent_price_per_sqm['apartment']) / len(rent_price_per_sqm['apartment']) if rent_price_per_sqm['apartment'] else 0
        avg_price_per_sqm_rent_commercial = sum(rent_price_per_sqm['commercial']) / len(rent_price_per_sqm['commercial']) if rent_price_per_sqm['commercial'] else 0
        
        conn.close()
        
        return {
            # Basic stats
            'total_listings': total_listings,
            'for_sale_available': for_sale_available,
            'for_sale_sold': for_sale_sold,
            'for_rent_available': for_rent_available,
            'for_rent_rented': for_rent_rented,
            'total_value': round(total_value, 2),
            'average_price': round(avg_price, 2),
            'min_price': round(min_price, 2),
            'max_price': round(max_price, 2),
            
            # Sale stats
            'sale_avg_price': round(sale_avg_price, 2),
            'sale_min_price': round(sale_min_price, 2),
            'sale_max_price': round(sale_max_price, 2),
            
            # Rent stats
            'rent_avg_price': round(rent_avg_price, 2),
            'rent_min_price': round(rent_min_price, 2),
            'rent_max_price': round(rent_max_price, 2),
            
            # Currency
            'currency': most_common_currency,
            'currencies_breakdown': dict(currencies),
            
            # Images
            'total_images': total_images,
            'avg_images_per_listing': round(avg_images, 1),
            
            # Dates
            'oldest_listing_date': oldest_date,
            'newest_listing_date': newest_date,
            'recent_listings': recent_listings,
            
            # Locations (legacy)
            'locations': [{'name': loc[0], 'count': loc[1]} for loc in location_counts],
            
            # === ENHANCED ANALYTICS ===
            
            # Property types
            'property_types_sale': dict(property_types_sale),
            'property_types_rent': dict(property_types_rent),
            
            # Rooms distribution
            'rooms_sale': dict(rooms_distribution_sale),
            'rooms_rent': dict(rooms_distribution_rent),
            
            # Surface area stats
            'avg_surface_sale': round(avg_surface_sale, 1),
            'avg_surface_rent': round(avg_surface_rent, 1),
            
            # Surface area by property type
            'avg_surface_sale_house': round(avg_surface_sale_house, 1),
            'avg_surface_sale_apartment': round(avg_surface_sale_apartment, 1),
            'avg_surface_sale_commercial': round(avg_surface_sale_commercial, 1),
            'avg_surface_rent_house': round(avg_surface_rent_house, 1),
            'avg_surface_rent_apartment': round(avg_surface_rent_apartment, 1),
            'avg_surface_rent_commercial': round(avg_surface_rent_commercial, 1),
            
            # Price per m² by property type
            'avg_price_per_sqm_sale_house': round(avg_price_per_sqm_sale_house, 2),
            'avg_price_per_sqm_sale_apartment': round(avg_price_per_sqm_sale_apartment, 2),
            'avg_price_per_sqm_sale_commercial': round(avg_price_per_sqm_sale_commercial, 2),
            'avg_price_per_sqm_rent_house': round(avg_price_per_sqm_rent_house, 2),
            'avg_price_per_sqm_rent_apartment': round(avg_price_per_sqm_rent_apartment, 2),
            'avg_price_per_sqm_rent_commercial': round(avg_price_per_sqm_rent_commercial, 2),
            
            # Price percentiles
            'sale_percentiles': {
                'p25': round(sale_percentiles['p25'], 2),
                'p50': round(sale_percentiles['p50'], 2),
                'p75': round(sale_percentiles['p75'], 2),
                'p90': round(sale_percentiles['p90'], 2)
            },
            'rent_percentiles': {
                'p25': round(rent_percentiles['p25'], 2),
                'p50': round(rent_percentiles['p50'], 2),
                'p75': round(rent_percentiles['p75'], 2),
                'p90': round(rent_percentiles['p90'], 2)
            },
            
            # Price per sqm
            'avg_price_per_sqm_sale': round(avg_price_per_sqm_sale, 2),
            'avg_price_per_sqm_rent': round(avg_price_per_sqm_rent, 2),
            
            # Top amenities
            'top_amenities_sale': [{'name': k, 'count': v} for k, v in amenities_sale.most_common(10)],
            'top_amenities_rent': [{'name': k, 'count': v} for k, v in amenities_rent.most_common(10)],
            
        }
        
    except sqlite3.Error as e:
        print(f"Database error in statistics: {e}")
        return None
    except Exception as e:
        print(f"Error calculating statistics: {e}")
        return None


def get_all_listings():
    """
    Fetch all listings from database with their first image.
    
    Returns:
        List of dictionaries containing listing data
    """
    try:
        conn = get_db_connection("/api/listings")
        cursor = conn.cursor()
        
        # Query listings with first image
        query = """
            SELECT 
                l.id,
                l.title_ro,
                l.title_ru,
                l.price_json,
                l.address,
                l.created_at,
                l.folder_path,
                l.status,
                l.sold,
                l.rented,
                l.listing_type,
                l.property_type,
                (SELECT local_path FROM listing_images 
                 WHERE listing_id = l.id 
                 ORDER BY position LIMIT 1) as first_image
            FROM listings l
            WHERE l.status = 'active'
            ORDER BY l.created_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Get all listing IDs for features query
        listing_ids = [dict(row)['id'] for row in rows]
        
        # Fetch features for all listings
        features_map = {}
        if listing_ids:
            placeholders = ','.join(['?' for _ in listing_ids])
            cursor.execute(f"""
                SELECT listing_id, feature_key, feature_value 
                FROM listing_features 
                WHERE listing_id IN ({placeholders})
            """, listing_ids)
            for feat_row in cursor.fetchall():
                lid, fkey, fval = feat_row
                if lid not in features_map:
                    features_map[lid] = {}
                if fkey and fval:
                    features_map[lid][fkey] = fval
        
        # Re-execute main query to get rows again
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convert rows to list of dicts
        listings = []
        for row in rows:
            listing = dict(row)
            
            # Add features
            listing['features'] = features_map.get(listing['id'], {})
            
            # Parse price JSON
            try:
                listing['price_obj'] = json.loads(listing['price_json']) if listing['price_json'] else {}
            except (json.JSONDecodeError, TypeError):
                listing['price_obj'] = {}
            
            # Get first price value for display
            listing['display_price'] = list(listing['price_obj'].values())[0] if listing['price_obj'] else "N/A"
            
            # Extract numeric price for sorting
            listing['price_numeric'] = 0
            if listing['price_obj']:
                first_price_str = list(listing['price_obj'].values())[0]
                # Extract numeric value from price string like "50,000 €" or "52000 $"
                import re
                numeric_match = re.search(r'[\d,]+', first_price_str)
                if numeric_match:
                    try:
                        listing['price_numeric'] = float(numeric_match.group().replace(',', ''))
                    except ValueError:
                        listing['price_numeric'] = 0
            
            # Get images for preview
            cursor.execute("""
                SELECT local_path FROM listing_images 
                WHERE listing_id = ? 
                ORDER BY position LIMIT 5
            """, (listing['id'],))
            listing['images'] = [img_row[0] for img_row in cursor.fetchall()]
            
            listings.append(listing)
        
        conn.close()
        return listings
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    except Exception as e:
        print(f"Error fetching listings: {e}")
        return []


@app.route('/')
def index():
    """Main dashboard page showing all listings in a grid."""
    listings = get_all_listings()
    return render_template('dashboard.html', listings=listings, count=len(listings))


@app.route('/api/statistics')
def api_statistics():
    """API endpoint that returns statistics as JSON."""
    stats = calculate_statistics()
    if stats:
        return jsonify(stats)
    else:
        return jsonify({'error': 'Failed to calculate statistics'}), 500


@app.route('/api/listings')
def api_listings():
    """API endpoint that returns all listings as JSON."""
    listings = get_all_listings()
    return jsonify({'success': True, 'listings': listings, 'count': len(listings)})


@app.route('/api/coordinates')
def api_coordinates():
    """API endpoint that returns all listing coordinates for mapping."""
    try:
        conn = get_db_connection("/api/coordinates")
        cursor = conn.cursor()
        
        query = """
            SELECT 
                lm.listing_id,
                lm.latitude,
                lm.longitude,
                lm.map_title,
                l.title_ro,
                l.title_ru,
                l.price_json,
                l.address,
                l.sold,
                l.rented,
                l.listing_type,
                l.property_type
            FROM listing_map lm
            JOIN listings l ON lm.listing_id = l.id
            WHERE l.status = 'active' 
            AND lm.latitude IS NOT NULL 
            AND lm.longitude IS NOT NULL
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        coordinates = []
        for row in rows:
            listing_data = dict(row)
            
            # Parse price
            try:
                price_obj = json.loads(listing_data['price_json']) if listing_data['price_json'] else {}
                display_price = list(price_obj.values())[0] if price_obj else "N/A"
            except (json.JSONDecodeError, TypeError, IndexError):
                display_price = "N/A"
            
            coordinates.append({
                'id': listing_data['listing_id'],
                'lat': listing_data['latitude'],
                'lng': listing_data['longitude'],
                'title_ro': listing_data['title_ro'],
                'title_ru': listing_data['title_ru'],
                'price': display_price,
                'address': listing_data['address'],
                'map_title': listing_data['map_title'],
                'sold': listing_data.get('sold', 'no'),
                'rented': listing_data.get('rented', 'no'),
                'listing_type': listing_data.get('listing_type', 'for_sale'),
                'property_type': listing_data.get('property_type', 'apartment')
            })
        
        conn.close()
        return jsonify({'coordinates': coordinates, 'count': len(coordinates)})
        
    except sqlite3.Error as e:
        print(f"Database error in coordinates: {e}")
        return jsonify({'error': 'Database error', 'coordinates': []}), 500
    except Exception as e:
        print(f"Error fetching coordinates: {e}")
        return jsonify({'error': 'Failed to fetch coordinates', 'coordinates': []}), 500


@app.route('/api/listings/<listing_id>/qr')
def api_listing_qr(listing_id):
    """API endpoint that generates QR code for a specific listing."""
    
    try:
        format = request.args.get('format', 'svg').lower()
        if format not in ['svg', 'png']:
            format = 'svg'
        
        conn = get_db_connection("/api/qr")
        cursor = conn.cursor()
        
        # Get listing data (listing_id can be string or numeric)
        query = """
            SELECT id, title_ro, title_ru, address, listing_type, property_type
            FROM listings 
            WHERE id = ?
        """
        
        cursor.execute(query, (str(listing_id),))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'Listing not found'}), 404
        
        listing_data = dict(row)
        conn.close()
        
        # Generate QR code
        qr_code = generate_qr_code(listing_data, format)
        
        if format == 'svg':
            # Return SVG as direct response
            return Response(
                qr_code,
                mimetype='image/svg+xml',
                headers={
                    'Content-Disposition': f'inline; filename="listing_{listing_id}.qr.svg"',
                    'Cache-Control': 'public, max-age=3600'  # Cache for 1 hour
                }
            )
        else:
            # Return PNG as JSON with base64
            return jsonify({
                'success': True,
                'qr_code': qr_code,
                'format': 'png',
            })
            
    except sqlite3.Error as e:
        print(f"Database error in QR generation: {e}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return jsonify({'error': 'Failed to generate QR code'}), 500


@app.route('/api/last_update')
def api_last_update():
    """API endpoint that returns the last update timestamp and listing count."""
    try:
        conn = get_db_connection("/api/last_update")
        cursor = conn.cursor()
        
        # Get the most recent updated_at timestamp and count
        cursor.execute("""
            SELECT 
                MAX(updated_at) as last_update,
                COUNT(*) as total_count
            FROM listings 
            WHERE status = 'active'
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'last_update': result['last_update'] if result else None,
            'total_count': result['total_count'] if result else 0,
            'timestamp': datetime.now().isoformat()
        })
        
    except sqlite3.Error as e:
        print(f"Database error in last_update: {e}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        print(f"Error fetching last_update: {e}")
        return jsonify({'error': 'Failed to fetch last update'}), 500


@app.route('/api/listings/<listing_id>/toggle-sold', methods=['POST'])
def api_toggle_sold(listing_id):
    """API endpoint to toggle the sold status of a listing."""
    try:
        conn = get_db_connection("/api/toggle-sold")
        cursor = conn.cursor()
        
        # Get current sold status
        cursor.execute('SELECT sold FROM listings WHERE id = ?', (listing_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        
        current_sold = row['sold'] or 'no'
        new_sold = 'yes' if current_sold == 'no' else 'no'
        
        # Update sold status - try with user field, fall back if column doesn't exist
        try:
            cursor.execute("""
                UPDATE listings 
                SET sold = ?, updated_at = ?, user = ?
                WHERE id = ?
            """, (new_sold, datetime.now().isoformat(), 'Dashboard', listing_id))
        except sqlite3.OperationalError:
            # user column doesn't exist yet, update without it
            cursor.execute("""
                UPDATE listings 
                SET sold = ?, updated_at = ?
                WHERE id = ?
            """, (new_sold, datetime.now().isoformat(), listing_id))
        
        conn.commit()
        conn.close()
        
        # Add journal entry
        action = 'sold' if new_sold == 'yes' else 'available'
        add_journal_entry(
            title=action,
            content='',
            entry_type='log',
            listing_id=listing_id,
            user='Dashboard'
        )
        
        return jsonify({'success': True, 'sold': new_sold})
        
    except sqlite3.Error as e:
        print(f"Database error toggling sold status: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        print(f"Error toggling sold status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listings/<listing_id>/toggle-rented', methods=['POST'])
def api_toggle_rented(listing_id):
    """API endpoint to toggle the rented status of a listing."""
    try:
        conn = get_db_connection("/api/toggle-rented")
        cursor = conn.cursor()
        
        # Get current rented status
        cursor.execute('SELECT rented FROM listings WHERE id = ?', (listing_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        
        current_rented = row['rented'] or 'no'
        new_rented = 'yes' if current_rented == 'no' else 'no'
        
        # Update rented status
        try:
            cursor.execute("""
                UPDATE listings 
                SET rented = ?, updated_at = ?, user = ?
                WHERE id = ?
            """, (new_rented, datetime.now().isoformat(), 'Dashboard', listing_id))
        except sqlite3.OperationalError:
            # user column doesn't exist yet, update without it
            cursor.execute("""
                UPDATE listings 
                SET rented = ?, updated_at = ?
                WHERE id = ?
            """, (new_rented, datetime.now().isoformat(), listing_id))
        
        conn.commit()
        conn.close()
        
        # Add journal entry
        action = 'rented' if new_rented == 'yes' else 'available'
        add_journal_entry(
            title=action,
            content='',
            entry_type='log',
            listing_id=listing_id,
            user='Dashboard'
        )
        
        return jsonify({'success': True, 'rented': new_rented})
        
    except sqlite3.Error as e:
        print(f"Database error toggling rented status: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        print(f"Error toggling rented status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/listings/<path:filepath>')
def serve_listing(filepath):
    """
    Serve static files from the Listings directory.
    This allows accessing listing HTML files and images.
    """
    try:
        return send_from_directory(LISTINGS_DIR, filepath)
    except FileNotFoundError:
        abort(404)


@app.route('/promotional/<path:filename>')
def serve_promotional(filename):
    """
    Serve promotional assets like logos.
    """
    try:
        promotional_dir = Path(__file__).parent / "Templates" / "Promotional"
        return send_from_directory(promotional_dir, filename)
    except FileNotFoundError:
        abort(404)


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return "<h1>404 - File Not Found</h1><p>The requested listing or file could not be found.</p>", 404


@app.route('/api/journal', methods=['GET'])
def api_get_journal():
    """API endpoint to get journal entries."""
    try:
        listing_id = request.args.get('listing_id')
        entry_type = request.args.get('entry_type')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        entries = get_journal_entries(
            listing_id=listing_id,
            entry_type=entry_type,
            limit=limit,
            offset=offset
        )
        
        return jsonify({'success': True, 'entries': entries, 'count': len(entries)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journal', methods=['POST'])
def api_add_journal():
    """API endpoint to add a journal entry."""
    try:
        data = request.get_json()
        
        result = add_journal_entry(
            title=data.get('title', ''),
            content=data.get('content', ''),
            entry_type=data.get('entry_type', 'log'),
            listing_id=data.get('listing_id'),
            user=data.get('user'),
            tags=data.get('tags')
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journal/<int:entry_id>', methods=['PUT'])
def api_update_journal(entry_id):
    """API endpoint to update a journal entry."""
    try:
        data = request.get_json()
        
        result = update_journal_entry(
            entry_id=entry_id,
            title=data.get('title'),
            content=data.get('content'),
            entry_type=data.get('entry_type'),
            tags=data.get('tags')
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journal/<int:entry_id>', methods=['DELETE'])
def api_delete_journal(entry_id):
    """API endpoint to delete a journal entry."""
    try:
        result = delete_journal_entry(entry_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journal/clear', methods=['DELETE'])
def api_clear_journal():
    """API endpoint to clear journal entries by age."""
    try:
        # Get age parameter from query string (e.g., '1week', '1month', 'all')
        age = request.args.get('age', 'all')
        
        conn = sqlite3.connect('Mainframe.db')
        cursor = conn.cursor()
        
        if age == 'all':
            cursor.execute('DELETE FROM journal_entries')
        elif age == '1week':
            # Delete entries older than 1 week
            cursor.execute("""
                DELETE FROM journal_entries 
                WHERE datetime(created_at) < datetime('now', '-7 days')
            """)
        elif age == '1month':
            # Delete entries older than 1 month
            cursor.execute("""
                DELETE FROM journal_entries 
                WHERE datetime(created_at) < datetime('now', '-30 days')
            """)
        else:
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid age parameter'}), 400
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'{deleted_count} journal entries cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>', methods=['GET'])
def api_get_listing(listing_id):
    """API endpoint to get listing details for editing."""
    try:
        listing = get_listing_from_mainframe(listing_id)
        if listing:
            # Check if the HTML file exists (indicates completion)
            project_root = Path(__file__).parent
            
            html_file = project_root / 'Listings' / listing_id / 'index.html'
            pwa_file = project_root / 'Listings' / listing_id / 'manifest.json'
            
            # Determine process completion status
            html_exists = html_file.exists()
            pwa_exists = pwa_file.exists()
            
            processes_completed = {
                'data_scraping': True,  # If listing exists, data was scraped
                'database_save': True,  # If listing exists, it's in database
                'html_generation': html_exists,
                'pwa_manifest': pwa_exists,
                'image_download': bool(listing.get('local_images')),
                'poi_fetch': bool(listing.get('poi_data'))
            }
            
            return jsonify({
                'success': True, 
                'listing': listing,
                'processes_completed': processes_completed,
                'is_complete': html_exists and pwa_exists  # Simple completion flag
            })
        else:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/status', methods=['GET'])
def api_listing_status(listing_id):
    """Simple status endpoint for polling completion."""
    try:
        project_root = Path(__file__).parent
        html_file = project_root / 'Listings' / listing_id / 'index.html'
        pwa_file = project_root / 'Listings' / listing_id / 'manifest.json'
        
        html_exists = html_file.exists()
        pwa_exists = pwa_file.exists()
        is_complete = html_exists and pwa_exists
        
        return jsonify({
            'success': True,
            'listing_id': listing_id,
            'html_generated': html_exists,
            'pwa_generated': pwa_exists,
            'is_complete': is_complete
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>', methods=['PUT'])
def api_update_listing(listing_id):
    """API endpoint to update listing fields."""
    try:
        data = request.get_json()
        updates = data.get('updates', {})
        user = data.get('user', 'Dashboard')
        regenerate = data.get('regenerate', True)
        changed_fields = data.get('changed_fields', [])
        
        print(f"\n{'='*60}")
        print(f"📝 UPDATE: Listing {listing_id}")
        print(f"{'='*60}")
        
        # Get original data for comparison
        original_listing = get_listing_from_mainframe(listing_id)
        
        # Show what changed (clean diff format)
        if 'features' in updates and original_listing:
            orig_features = original_listing.get('features', {})
            new_features = updates.get('features', {})
            
            # Compare RO features only (RU mirrors RO)
            orig_ro = {}
            new_ro = {}
            
            # Flatten original features
            for section, items in orig_features.get('ro', {}).items():
                if isinstance(items, dict):
                    orig_ro.update(items)
            
            # Flatten new features
            for section, items in new_features.get('ro', {}).items():
                if isinstance(items, dict):
                    new_ro.update(items)
            
            # Find actual changes
            for key in set(orig_ro.keys()) | set(new_ro.keys()):
                old_val = orig_ro.get(key, '—')
                new_val = new_ro.get(key, '—')
                if old_val != new_val:
                    print(f"  📌 {key}: \"{old_val}\" → \"{new_val}\"")
        
        if 'amenities' in updates and original_listing:
            orig_amenities = set(original_listing.get('amenities', {}).get('ro', {}).keys())
            new_amenities = set(updates.get('amenities', {}).get('ro', {}).keys())
            
            added = new_amenities - orig_amenities
            removed = orig_amenities - new_amenities
            
            for a in added:
                print(f"  ✅ Amenity added: {a}")
            for a in removed:
                print(f"  ❌ Amenity removed: {a}")
        
        # Show simple field changes
        simple_fields = ['title_ro', 'title_ru', 'contact', 'price_json', 'listing_type', 'property_type']
        for field in simple_fields:
            if field in updates and original_listing:
                old_val = original_listing.get(field, '—')
                new_val = updates.get(field, '—')
                if old_val != new_val:
                    # Truncate long values
                    old_display = str(old_val)[:50] + '...' if len(str(old_val)) > 50 else old_val
                    new_display = str(new_val)[:50] + '...' if len(str(new_val)) > 50 else new_val
                    print(f"  📌 {field}: \"{old_display}\" → \"{new_display}\"")
        
        print(f"{'='*60}")
        
        # Update database
        result = update_listing_fields(listing_id, updates, user, changed_fields)
        
        if result['success'] and regenerate:
            # Regenerate HTML
            print(f"🔄 Regenerating HTML for listing {listing_id}...")
            try:
                regen_success = regenerate_listing_by_id(
                    listing_id,
                    refetch_pois=False  # Don't refetch POIs unless address changed
                )
                result['html_regenerated'] = regen_success
                if regen_success:
                    print(f"✅ HTML regenerated successfully")
                else:
                    print(f"⚠️  HTML regeneration returned False")
            except Exception as e:
                result['html_regenerated'] = False
                result['regeneration_error'] = str(e)
                print(f"❌ HTML regeneration failed: {e}")
        elif not regenerate:
            print(f"⏭️  Skipping HTML regeneration (regenerate=False)")
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>', methods=['DELETE'])
def api_delete_listing(listing_id):
    """API endpoint to delete a listing completely."""
    try:
        import shutil
        
        # Delete from database
        from Helper.database import delete_listing_from_mainframe
        db_success = delete_listing_from_mainframe(listing_id)
        
        if not db_success:
            return jsonify({'success': False, 'error': 'Failed to delete from database'}), 500
        
        # Delete listing folder
        listing_folder = LISTINGS_DIR / listing_id
        folder_deleted = False
        if listing_folder.exists():
            try:
                shutil.rmtree(listing_folder)
                folder_deleted = True
            except Exception as e:
                print(f"⚠️  Warning: Could not delete folder {listing_folder}: {e}")
                # Continue anyway since DB deletion succeeded
        
        return jsonify({
            'success': True,
            'database_deleted': db_success,
            'folder_deleted': folder_deleted
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/images', methods=['GET'])
def api_get_listing_images(listing_id):
    """API endpoint to get images for a listing."""
    try:
        listing_folder = LISTINGS_DIR / listing_id
        images_folder = listing_folder / 'images'
        
        if not images_folder.exists():
            return jsonify({'success': True, 'images': []})
        
        # Try to get image order from database first
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                SELECT local_path FROM listing_images 
                WHERE listing_id = ? 
                ORDER BY position
            ''', (listing_id,))
            db_images = [row[0] for row in c.fetchall() if row[0]]
            conn.close()
            
            # Verify images exist on disk
            if db_images:
                valid_images = []
                for img_path in db_images:
                    full_path = listing_folder / img_path
                    if full_path.exists():
                        valid_images.append(img_path)
                
                if valid_images:
                    return jsonify({
                        'success': True,
                        'images': valid_images,
                        'count': len(valid_images)
                    })
        except Exception as db_error:
            print(f"Warning: Could not get image order from database: {db_error}")
        
        # Fallback: Get all image files from filesystem
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        images = []
        
        for file_path in images_folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                # Return relative path from listing folder
                relative_path = f"images/{file_path.name}"
                images.append(relative_path)
        
        # Sort images by name (usually numbered)
        images.sort()
        
        return jsonify({
            'success': True,
            'images': images,
            'count': len(images)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/images/reorder', methods=['PUT'])
def api_reorder_listing_images(listing_id):
    """API endpoint to reorder images for a listing."""
    try:
        data = request.get_json()
        image_order = data.get('image_order', [])
        
        if not image_order:
            return jsonify({'success': False, 'error': 'No image order provided'}), 400
        
        # Update image order in database
        result = update_image_order(listing_id, image_order)
        
        if result['success']:
            # Regenerate HTML to reflect new image order
            print(f"🔄 Regenerating HTML after image reorder for listing {listing_id}...")
            try:
                regen_success = regenerate_listing_by_id(listing_id, refetch_pois=False)
                result['html_regenerated'] = regen_success
                if regen_success:
                    print(f"✅ HTML regenerated successfully")
                else:
                    print(f"⚠️  HTML regeneration returned False")
            except Exception as e:
                result['html_regenerated'] = False
                result['regeneration_error'] = str(e)
                print(f"❌ HTML regeneration failed: {e}")
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/poi', methods=['GET'])
def api_get_listing_poi(listing_id):
    """API endpoint to get POI data for a listing."""
    try:
        from Helper.database import get_poi_data_from_mainframe
        
        poi_data = get_poi_data_from_mainframe(listing_id)
        
        if poi_data:
            return jsonify({
                'success': True,
                'poi_data': poi_data
            })
        else:
            return jsonify({
                'success': True,
                'poi_data': {}
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/refresh-pois', methods=['POST'])
def api_refresh_listing_pois(listing_id):
    """
    API endpoint to complete/merge POI data for a listing.
    Only adds missing categories or fills incomplete ones - doesn't replace existing data.
    Preserves original category key structure.
    """
    try:
        from Helper.database import get_listing_from_mainframe, save_poi_data_to_mainframe, get_poi_data_from_mainframe
        from Helper.poi_fetcher import POIFetcher
        import asyncio
        
        # Get listing to get coordinates
        listing = get_listing_from_mainframe(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        
        map_data = listing.get('map_data')
        if not map_data or not map_data.get('lat') or not map_data.get('lng'):
            return jsonify({'success': False, 'error': 'No coordinates available for this listing'}), 400
        
        lat = map_data['lat']
        lng = map_data['lng']
        
        # Get existing POI data (preserve original keys)
        existing_pois = get_poi_data_from_mainframe(listing_id) or {}
        
        print(f"\n📍 Completing POIs for listing {listing_id} at ({lat}, {lng})")
        print(f"   Existing categories: {list(existing_pois.keys())}")
        
        # Define expected categories and their max POIs
        poi_fetcher = POIFetcher(verbose=False)
        max_per_category = poi_fetcher.max_pois_per_group
        
        # Calculate total POIs per parent group (sum of all child categories)
        existing_counts = {}
        for parent_cat, children in poi_fetcher.parent_to_children.items():
            count = len(existing_pois.get(parent_cat, []))
            for child in children:
                count += len(existing_pois.get(child, []))
            existing_counts[parent_cat] = count
        
        # Find incomplete parent categories
        incomplete_categories = [cat for cat, count in existing_counts.items() if count < max_per_category]
        
        if not incomplete_categories:
            print(f"   ✅ All POI categories are complete")
            total_pois = sum(len(pois) for pois in existing_pois.values())
            return jsonify({
                'success': True,
                'poi_count': total_pois,
                'poi_data': existing_pois,
                'message': 'All categories already complete'
            })
        
        print(f"   Incomplete categories: {incomplete_categories}")
        print(f"   Current counts: {existing_counts}")
        
        # Fetch new POI data (returns child category keys like 'kindergartens', 'hospitals')
        new_poi_data = asyncio.run(poi_fetcher.fetch_all_pois_for_location(lat, lng))
        
        # Start with a DEEP COPY of ALL existing data (preserve everything including keys)
        merged_pois = {k: list(v) for k, v in existing_pois.items()}
        added_count = 0
        
        # Collect all existing POI names across all categories to avoid duplicates
        all_existing_names = set()
        for pois in existing_pois.values():
            for poi in pois:
                name = poi.get('name', '').lower()
                if name:
                    all_existing_names.add(name)
        
        # Add new POIs to their respective child categories (preserve original structure)
        for parent_cat in incomplete_categories:
            children = poi_fetcher.parent_to_children.get(parent_cat, [parent_cat])
            current_total = existing_counts[parent_cat]
            space_left = max_per_category - current_total
            
            if space_left <= 0:
                continue
            
            added_to_parent = 0
            
            for child in children:
                new_child_pois = new_poi_data.get(child, [])
                if not new_child_pois:
                    continue
                
                # Initialize child category if it doesn't exist
                if child not in merged_pois:
                    merged_pois[child] = []
                
                # Add new POIs to this child category
                for poi in new_child_pois:
                    if added_to_parent >= space_left:
                        break
                    
                    poi_name = poi.get('name', '').lower()
                    if poi_name and poi_name not in all_existing_names:
                        merged_pois[child].append(poi)
                        all_existing_names.add(poi_name)
                        added_count += 1
                        added_to_parent += 1
            
            if added_to_parent > 0:
                print(f"   ✅ {parent_cat}: added {added_to_parent} new POIs")
        
        # Only save if we actually added something, otherwise preserve existing data
        if added_count > 0:
            save_poi_data_to_mainframe(listing_id, merged_pois)
            
            # Regenerate HTML to include new POI data
            try:
                regen_result = regenerate_listing_by_id(listing_id, refetch_pois=False)
                print(f"   🔄 HTML regenerated: {regen_result}")
            except Exception as e:
                print(f"⚠️ Warning: Could not regenerate HTML: {e}")
        else:
            print(f"   ℹ️ No new POIs found to add")
        
        total_pois = sum(len(pois) for pois in merged_pois.values())
        
        return jsonify({
            'success': True,
            'poi_count': total_pois,
            'added_count': added_count,
            'poi_data': merged_pois
        })
            
    except Exception as e:
        print(f"❌ Error refreshing POIs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/update-address', methods=['POST'])
def api_update_listing_address(listing_id):
    """
    API endpoint to update listing address using interactive map overlay.
    Opens a map for the user to select a new location, then updates coordinates and re-fetches POIs.
    """
    try:
        from Helper.database import get_listing_from_mainframe, save_poi_data_to_mainframe
        from Helper.map_overlay import create_interactive_map
        from Helper.poi_fetcher import POIFetcher
        import asyncio
        import sqlite3
        
        # Get listing to get current coordinates
        listing = get_listing_from_mainframe(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        
        map_data = listing.get('map_data', {})
        current_lat = map_data.get('lat', 47.0105) if map_data else 47.0105
        current_lng = map_data.get('lng', 28.8638) if map_data else 28.8638
        current_address = listing.get('display_address', listing.get('address', 'Unknown address'))
        
        print(f"\n🗺️ Opening map overlay for address update - Listing {listing_id}")
        print(f"   Current: {current_address} ({current_lat}, {current_lng})")
        
        # Open interactive map for user to select new location
        result = create_interactive_map(
            original_address=current_address,
            estimated_lat=current_lat,
            estimated_lng=current_lng
        )
        
        if result is None:
            # User cancelled
            print(f"   ❌ User cancelled address selection")
            return jsonify({
                'success': True,
                'cancelled': True,
                'address_updated': False
            })
        
        new_lat, new_lng, new_address = result
        print(f"   ✅ New location selected: {new_address} ({new_lat}, {new_lng})")
        
        # Update the listing's map_data in database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Update address fields in listings table
        c.execute('''
            UPDATE listings 
            SET address = ?, display_address = ?, geocoding_address = ?, updated_at = ?
            WHERE id = ?
        ''', (new_address, new_address, new_address, 
              datetime.now().isoformat(), listing_id))
        
        # Update or insert map data in listing_map table
        c.execute('SELECT listing_id FROM listing_map WHERE listing_id = ?', (listing_id,))
        row = c.fetchone()
        if row:
            c.execute('''
                UPDATE listing_map 
                SET latitude = ?, longitude = ?, map_title = ?
                WHERE listing_id = ?
            ''', (new_lat, new_lng, new_address, listing_id))
        else:
            c.execute('''
                INSERT INTO listing_map (listing_id, latitude, longitude, map_title)
                VALUES (?, ?, ?, ?)
            ''', (listing_id, new_lat, new_lng, new_address))
        
        conn.commit()
        conn.close()
        
        print(f"   📝 Database updated with new address")
        
        # Re-fetch POIs for the new location
        print(f"   🔄 Fetching POIs for new location...")
        try:
            poi_fetcher = POIFetcher(verbose=False)
            new_poi_data = asyncio.run(poi_fetcher.fetch_all_pois_for_location(new_lat, new_lng))
            
            if new_poi_data:
                save_poi_data_to_mainframe(listing_id, new_poi_data, verbose=False)
                total_pois = sum(len(pois) for pois in new_poi_data.values())
                print(f"   ✅ Saved {total_pois} POIs for new location")
            else:
                print(f"   ⚠️ No POIs found for new location")
        except Exception as poi_error:
            print(f"   ⚠️ Error fetching POIs: {poi_error}")
        
        # Regenerate HTML
        try:
            regen_result = regenerate_listing_by_id(listing_id, refetch_pois=False)
            print(f"   🔄 HTML regenerated: {regen_result}")
        except Exception as regen_error:
            print(f"   ⚠️ Warning: Could not regenerate HTML: {regen_error}")
        
        return jsonify({
            'success': True,
            'address_updated': True,
            'new_address': new_address,
            'new_lat': new_lat,
            'new_lng': new_lng
        })
        
    except Exception as e:
        print(f"❌ Error updating address: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/<listing_id>/upload-images', methods=['POST'])
def api_upload_listing_images(listing_id):
    """API endpoint to upload images for a listing."""
    try:
        # Check if listing exists
        listing_folder = LISTINGS_DIR / listing_id
        if not listing_folder.exists():
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        
        # Create images folder if it doesn't exist
        images_folder = listing_folder / 'images'
        images_folder.mkdir(exist_ok=True)
        
        # Check if files were uploaded
        if 'images' not in request.files:
            return jsonify({'success': False, 'error': 'No images provided'}), 400
        
        files = request.files.getlist('images')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'success': False, 'error': 'No images selected'}), 400
        
        uploaded_files = []
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        
        from PIL import Image
        from io import BytesIO
        import uuid
        
        for file in files:
            if file and file.filename:
                # Check file extension
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in allowed_extensions:
                    continue
                
                # Generate unique filename
                unique_id = uuid.uuid4().hex[:8]
                
                # Convert to WebP format
                try:
                    img_bytes = file.read()
                    img = Image.open(BytesIO(img_bytes))
                    
                    # Convert RGBA to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode in ('RGBA', 'LA'):
                            background.paste(img, mask=img.split()[-1])
                            img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Save as WebP
                    webp_filename = f"{unique_id}_{Path(file.filename).stem}.webp"
                    file_path = images_folder / webp_filename
                    img.save(file_path, 'WEBP', quality=100, method=6)
                    uploaded_files.append(webp_filename)
                    
                except Exception as e:
                    # Fallback: save original if WebP conversion fails
                    print(f"⚠️  WebP conversion failed, saving original: {e}")
                    file.seek(0)
                    original_filename = f"{unique_id}_{file.filename}"
                    file_path = images_folder / original_filename
                    file.save(str(file_path))
                    uploaded_files.append(original_filename)
        
        if not uploaded_files:
            return jsonify({'success': False, 'error': 'No valid image files uploaded'}), 400
        
        return jsonify({
            'success': True,
            'uploaded_files': uploaded_files,
            'count': len(uploaded_files),
            'message': f'Successfully uploaded {len(uploaded_files)} image(s)'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listing/create', methods=['POST'])
def api_create_listing():
    """API endpoint to manually create a new listing."""
    try:
        data = request.get_json()
        
        # Import required modules
        from Helper.database import save_listing_to_mainframe
        import uuid
        
        # Generate unique listing ID
        listing_id = str(uuid.uuid4())[:8]
        
        # Create listing folder
        listing_folder = LISTINGS_DIR / listing_id
        listing_folder.mkdir(parents=True, exist_ok=True)
        images_folder = listing_folder / 'images'
        images_folder.mkdir(exist_ok=True)
        
        # Handle image uploads (base64 encoded) - convert to WebP for optimization
        image_files = []
        images_data = data.get('images', [])
        if images_data:
            import base64
            from PIL import Image
            from io import BytesIO
            
            for idx, img_data in enumerate(images_data):
                try:
                    # Extract base64 data (remove data:image/...;base64, prefix)
                    base64_str = img_data['data'].split(',')[1] if ',' in img_data['data'] else img_data['data']
                    img_bytes = base64.b64decode(base64_str)
                    
                    # Convert to WebP format
                    try:
                        img = Image.open(BytesIO(img_bytes))
                        
                        # Convert RGBA to RGB if necessary
                        if img.mode in ('RGBA', 'LA', 'P'):
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            if img.mode in ('RGBA', 'LA'):
                                background.paste(img, mask=img.split()[-1])
                                img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # Save as WebP
                        img_filename = f"image_{idx}.webp"
                        img_path = images_folder / img_filename
                        img.save(img_path, 'WEBP', quality=100, method=6)
                        
                    except Exception as e:
                        # Fallback: save as original format if WebP conversion fails
                        print(f"⚠️  WebP conversion failed for image {idx}, saving as jpg: {e}")
                        img_filename = f"{idx}.jpg"
                        img_path = images_folder / img_filename
                        with open(img_path, 'wb') as f:
                            f.write(img_bytes)
                    
                    image_files.append(f"images/{img_filename}")
                except Exception as e:
                    print(f"⚠️  Error saving image {idx}: {e}")
        
        # Get title and description (could be dict or string)
        title_data = data.get('title', {})
        description_data = data.get('description', {})
        
        # Extract features and amenities from data
        features_data = data.get('features', {})
        amenities_data = data.get('amenities', {})
        
        # Ensure features and amenities are properly structured
        # Features should be nested under "Caracteristici" section for proper display
        features_ro = features_data.get('ro', {}) if isinstance(features_data, dict) else {}
        features_ru = features_data.get('ru', {}) if isinstance(features_data, dict) else {}
        
        # Wrap features in section if they exist
        if features_ro:
            features_ro = {'Caracteristici': features_ro}
        if features_ru:
            features_ru = {'Характеристики': features_ru}
        
        amenities_ro = amenities_data.get('ro', {}) if isinstance(amenities_data, dict) else {}
        amenities_ru = amenities_data.get('ru', {}) if isinstance(amenities_data, dict) else {}
        
        # Create localized structure
        localized = {
            'ro': {
                'title': title_data.get('ro', '') if isinstance(title_data, dict) else title_data,
                'description': description_data.get('ro', '') if isinstance(description_data, dict) else description_data,
                'features': features_ro,
                'amenities': amenities_ro
            },
            'ru': {
                'title': title_data.get('ru', '') if isinstance(title_data, dict) else title_data,
                'description': description_data.get('ru', '') if isinstance(description_data, dict) else description_data,
                'features': features_ru,
                'amenities': amenities_ru
            }
        }
        
        # Geocode address if provided (with interactive map for incomplete addresses)
        map_data = None
        if data.get('address'):
            try:
                import asyncio
                import re
                from Agent import geocode_with_cache, geocode_address
                from Helper.map_overlay import create_interactive_map
                
                address = data.get('address')
                
                # Check if address has a building number
                address_last_part = address.split(',')[-1] if ',' in address else address
                has_building_number = bool(re.search(r'\b\d+[A-Za-z]?(/\d+)?\b', address_last_part))
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                if has_building_number:
                    # Use cache for complete addresses
                    map_data = loop.run_until_complete(
                        geocode_with_cache(address, address, str(DB_PATH))
                    )
                else:
                    # For incomplete addresses, use full geocoding with interactive map
                    print(f"⚠️  Address missing building number: {address}")
                    print("   Opening interactive map for verification...")
                    
                    # Get estimated coordinates (skip internal map - we'll handle it ourselves)
                    temp_result = loop.run_until_complete(
                        geocode_address(address, address, skip_interactive_map=True)
                    )
                    
                    if temp_result:
                        # Show interactive map for user to confirm/correct location
                        map_result = create_interactive_map(
                            address,
                            temp_result['lat'],
                            temp_result['lng']
                        )
                        
                        if map_result:
                            # Unpack tuple
                            corrected_lat, corrected_lng, corrected_address = map_result
                            map_data = {
                                'lat': corrected_lat,
                                'lng': corrected_lng,
                                'title': corrected_address
                            }
                            # Update address with corrected one
                            data['address'] = corrected_address
                            print(f"✅ User selected: {corrected_address}")
                        else:
                            # User skipped
                            map_data = temp_result
                
                loop.close()
                
                if map_data:
                    print(f"✅ Geocoded address: {map_data['lat']}, {map_data['lng']}")
            except Exception as e:
                print(f"⚠️  Geocoding failed: {e}")
        
        # Build listing data structure with properly formatted features
        listing_data = {
            'id': listing_id,
            'url': data.get('url', ''),
            'domain': 'manual',
            'title': localized['ro']['title'],  # Use RO as primary
            'description': localized['ro']['description'],
            'price': data.get('price', {}),
            'address': data.get('address', ''),
            'contact': data.get('contact', ''),
            'images': image_files,
            'local_images': image_files,
            'features': {'ro': features_ro, 'ru': features_ru},
            'amenities': {'ro': amenities_ro, 'ru': amenities_ru},
            'standard_features': data.get('standard_features', {}),
            'localized': localized,
            'map_data': map_data,
            'listing_type': data.get('listing_type', 'for_sale'),
            'property_type': data.get('property_type', 'apartment'),
            'template_name': data.get('template_name', 'luna'),
            'folder_path': f'Listings/{listing_id}'
        }
        
        # Save to database
        success = save_listing_to_mainframe(listing_data)
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to save to database'}), 500
        
        # Fetch POI data if we have coordinates
        poi_fetched = False
        if map_data and map_data.get('lat') and map_data.get('lng'):
            try:
                from Helper.poi_fetcher import fetch_pois_for_listing
                from Helper.database import save_poi_data_to_mainframe
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                poi_data, poi_summary = loop.run_until_complete(
                    fetch_pois_for_listing(
                        float(map_data['lat']),
                        float(map_data['lng']),
                        radius=500,
                        verbose=False
                    )
                )
                loop.close()
                
                if poi_data:
                    save_poi_data_to_mainframe(listing_id, poi_data, radius=500, verbose=False)
                    print(f"✅ Fetched {poi_summary.get('total_pois', 0)} POIs")
                    poi_fetched = True
            except Exception as e:
                print(f"⚠️  POI fetching failed: {e}")
        
        # Generate HTML (don't refetch POIs if we just fetched them)
        try:
            regen_success = regenerate_listing_by_id(
                listing_id,
                refetch_pois=False  # POIs already fetched above
            )
            
            if not regen_success:
                print(f"⚠️  Warning: HTML generation failed for listing {listing_id}")
        except Exception as e:
            print(f"⚠️  Warning: HTML generation error: {e}")
        
        # Generate PWA manifest
        try:
            from pwa.manifest_generator import create_pwa_manifest
            import os
            
            pwa_data = {
                'id': listing_id,
                'title': localized['ro']['title'] or localized['ru']['title'] or 'Property Listing',
                'description': localized['ro']['description'] or localized['ru']['description'] or 'Real estate property listing',
                'price': ' '.join(data.get('price', {}).values()) if data.get('price') else '',
                'location': data.get('address', ''),
                'type': data.get('property_type', 'apartment'),
                'images': [os.path.basename(img) for img in image_files] if image_files else [],
                'coordinates': [map_data['lat'], map_data['lng']] if map_data else None,
                'phone': data.get('contact', ''),
                'timestamp': '',
                'lang': 'ro'
            }
            
            manifest_path = create_pwa_manifest(pwa_data, str(listing_folder), '')
            print(f"✅ PWA manifest generated")
        except Exception as e:
            print(f"⚠️  PWA manifest generation failed: {e}")
        
        # Add journal entry
        add_journal_entry(
            title='created',
            content=f"Listing created manually via dashboard",
            entry_type='log',
            listing_id=listing_id,
            user='Dashboard'
        )
        
        # Fetch the complete listing data from database
        from Helper.database import get_listing_from_mainframe
        listing_data = get_listing_from_mainframe(listing_id)
        
        return jsonify({
            'success': True,
            'listing_id': listing_id,
            'listing': listing_data,
            'message': 'Listing created successfully'
        })
        
    except Exception as e:
        print(f"Error creating listing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates', methods=['GET'])
def api_get_templates():
    """API endpoint to get available templates with multilingual support."""
    try:
        from Helper.builder import get_available_templates, TEMPLATE_REGISTRY
        
        # Get language from query parameter (default: 'ro')
        lang = request.args.get('lang', 'ro').lower()
        if lang not in ['en', 'ro', 'ru']:
            lang = 'ro'  # fallback to Romanian
        
        templates = []
        available_names = get_available_templates()
        
        for name in available_names:
            template_info = TEMPLATE_REGISTRY.get(name, {})
            descriptions = template_info.get('descriptions', {})
            
            # Get description for the requested language, with fallbacks
            description = descriptions.get(lang, descriptions.get('ro', descriptions.get('en', 'No description available')))
            
            templates.append({
                'name': name,
                'description': description,
                'icon': get_template_icon(name)
            })
        
        return jsonify({
            'success': True,
            'templates': templates,
            'language': lang
        })
    except Exception as e:
        print(f"Error fetching templates: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def get_template_icon(template_name):
    """Get icon emoji for template."""
    icons = {
        'luna': '🌙',
        'nova': '✨',
        'solar': '☀️',
        'aurora': '🌌',
        'zenith': '⭐',
        'horizon': '🌅',
        'eclipse': '🌑',
        'stellar': '💫'
    }
    return icons.get(template_name.lower(), '🏠')


@app.route('/api/listing/scrape', methods=['POST'])
def api_scrape_listing():
    """API endpoint to scrape a listing from a URL using Agent.py."""
    try:
        data = request.get_json()
        url = data.get('url')
        template_name = data.get('template_name', 'luna')  # Default to luna
        
        if not url:
            return jsonify({'success': False, 'error': 'URL is required'}), 400
        
        # Validate URL format
        if '999.md' not in url:
            return jsonify({'success': False, 'error': 'Only 999.md URLs are supported'}), 400
        
        # Import the scraper wrapper
        from Helper.scraper_wrapper import scrape_listing_from_url
        
        # Run the scraper (this will be async)
        result = scrape_listing_from_url(url, template_name)
        
        if result['success']:
            # Fetch the complete listing data from database
            from Helper.database import get_listing_from_mainframe
            listing_data = get_listing_from_mainframe(result['listing_id'])
            
            return jsonify({
                'success': True,
                'listing_id': result['listing_id'],
                'listing': listing_data,
                'processes_completed': result.get('processes_completed', {}),
                'message': 'Listing scraped and created successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error occurred')
            }), 500
            
    except Exception as e:
        print(f"Error scraping listing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def build_express_query(filters: dict) -> tuple:
    """
    Build a parameterized SQL query for express search filtering.
    
    Args:
        filters: Dictionary containing filter parameters:
            - property_type: apartment|house|commercial
            - listing_type: for_sale|for_rent
            - price_min: minimum price (numeric)
            - price_max: maximum price (numeric)
            - features: dict of feature_key: feature_value pairs
            - amenities: dict of amenity_key: True pairs (checkboxes)
            - limit: max results to return
            - offset: pagination offset
    
    Returns:
        Tuple of (sql_query, count_query, parameters_list)
    """
    params = []
    where_clauses = ["l.status = 'active'"]
    
    # Property type filter
    property_type = filters.get('property_type', 'apartment')
    if property_type in ('apartment', 'house', 'commercial'):
        where_clauses.append("l.property_type = ?")
        params.append(property_type)
    
    # Listing type filter
    listing_type = filters.get('listing_type', 'for_sale')
    if listing_type in ('for_sale', 'for_rent'):
        where_clauses.append("l.listing_type = ?")
        params.append(listing_type)
    
    # Price range filter - extract numeric price from price_json
    price_min = filters.get('price_min', 0)
    price_max = filters.get('price_max', 999999999)
    
    # We need to extract numeric price from price_json for comparison
    # price_json format: {"EUR": "50,000 €"} or {"MDL": "1,000,000 MDL"}
    where_clauses.append("""
        CAST(
            REPLACE(REPLACE(REPLACE(REPLACE(
                SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
            ',', ''), ' ', ''), '€', ''), '"', '')
        AS INTEGER) BETWEEN ? AND ?
    """)
    params.append(price_min)
    params.append(price_max)
    
    # Price per m² filter - calculate from price and surface area
    price_m2_min = filters.get('price_m2_min', 0)
    price_m2_max = filters.get('price_m2_max', 999999)
    
    # Only apply filter if user has restricted the range (not at 0 to max)
    # We apply if min > 0 OR if max is significantly less than a high threshold
    # This allows filtering even when max is set to a reasonable value
    if price_m2_min > 0 or (price_m2_max > 0 and price_m2_max < 50000):
        where_clauses.append("""
            (
                NOT EXISTS (
                    SELECT 1 FROM listing_features lf_area
                    WHERE lf_area.listing_id = l.id
                    AND lf_area.lang = 'ro'
                    AND lf_area.feature_key = 'Suprafață totală'
                    AND lf_area.feature_value IS NOT NULL
                    AND lf_area.feature_value != ''
                    AND CAST(lf_area.feature_value AS REAL) > 0
                )
                OR
                EXISTS (
                    SELECT 1 FROM listing_features lf_area
                    WHERE lf_area.listing_id = l.id
                    AND lf_area.lang = 'ro'
                    AND lf_area.feature_key = 'Suprafață totală'
                    AND lf_area.feature_value IS NOT NULL
                    AND lf_area.feature_value != ''
                    AND CAST(lf_area.feature_value AS REAL) > 0
                    AND (
                        CAST(
                            REPLACE(REPLACE(REPLACE(REPLACE(
                                SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                            ',', ''), ' ', ''), '€', ''), '"', '')
                        AS REAL)
                        /
                        CAST(lf_area.feature_value AS REAL)
                    ) BETWEEN ? AND ?
                )
            )
        """)
        params.append(price_m2_min)
        params.append(price_m2_max)
    
    # Feature filters - join with listing_features table
    # Use Romanian features (lang='ro') since frontend uses Romanian keys
    features = filters.get('features', {})
    feature_conditions = []
    for feature_key, feature_value in features.items():
        if feature_value and feature_value.strip():
            feature_conditions.append("""
                EXISTS (
                    SELECT 1 FROM listing_features lf 
                    WHERE lf.listing_id = l.id 
                    AND lf.lang = 'ro'
                    AND lf.feature_key = ? 
                    AND lf.feature_value = ?
                )
            """)
            params.append(feature_key)
            params.append(feature_value)
    
    if feature_conditions:
        where_clauses.extend(feature_conditions)
    
    # Amenity filters - join with listing_amenities table
    # Use Romanian amenities (lang='ro') since frontend uses Romanian keys
    amenities = filters.get('amenities', {})
    for amenity_key, is_checked in amenities.items():
        if is_checked:
            where_clauses.append("""
                EXISTS (
                    SELECT 1 FROM listing_amenities la 
                    WHERE la.listing_id = l.id 
                    AND la.lang = 'ro'
                    AND la.amenity_key = ?
                )
            """)
            params.append(amenity_key)
    
    # Location filter - use Haversine formula to calculate distance
    location_lat = filters.get('location_lat')
    location_lng = filters.get('location_lng')
    location_radius = filters.get('location_radius', 10)  # km
    
    # Always join with listing_map to get coordinates for map display
    location_join = " LEFT JOIN listing_map lm ON lm.listing_id = l.id"
    location_select = ", lm.latitude, lm.longitude"
    order_by = "l.created_at DESC"
    
    if location_lat is not None and location_lng is not None:
        # Add distance filter using equirectangular approximation
        where_clauses.append("""
            lm.latitude IS NOT NULL AND lm.longitude IS NOT NULL
            AND (
                111.32 * SQRT(
                    POW(lm.latitude - ?, 2) + 
                    POW((lm.longitude - ?) * COS(lm.latitude * 0.0174533), 2)
                )
            ) <= ?
        """)
        params.append(location_lat)
        params.append(location_lng)
        params.append(location_radius)
        
        # Add distance to select for sorting
        location_select = f""", lm.latitude, lm.longitude,
            111.32 * SQRT(
                POW(lm.latitude - {location_lat}, 2) + 
                POW((lm.longitude - {location_lng}) * COS(lm.latitude * 0.0174533), 2)
            ) as distance_km"""
        
        # Order by distance (closest first)
        order_by = "distance_km ASC"
    
    where_sql = " AND ".join(where_clauses)
    
    # Main query to get listings with first image and surface area
    select_sql = f"""
        SELECT DISTINCT
            l.id,
            l.title_ro,
            l.title_ru,
            l.address,
            l.price_json,
            l.property_type,
            l.listing_type,
            (SELECT local_path FROM listing_images 
             WHERE listing_id = l.id 
             ORDER BY position LIMIT 1) as first_image,
            (SELECT CAST(lf_area.feature_value AS REAL) 
             FROM listing_features lf_area 
             WHERE lf_area.listing_id = l.id 
             AND lf_area.lang = 'ro' 
             AND lf_area.feature_key = 'Suprafață totală'
             AND lf_area.feature_value IS NOT NULL 
             AND lf_area.feature_value != ''
             LIMIT 1) as surface_area
            {location_select}
        FROM listings l
        {location_join}
        WHERE {where_sql}
        ORDER BY {order_by}
    """
    
    # Count query for total results
    count_sql = f"""
        SELECT COUNT(DISTINCT l.id)
        FROM listings l
        {location_join}
        WHERE {where_sql}
    """
    
    # Add limit and offset for main query
    limit = filters.get('limit', 5)
    offset = filters.get('offset', 0)
    select_sql += " LIMIT ? OFFSET ?"
    
    # Parameters for select query (includes limit/offset)
    select_params = params + [limit, offset]
    # Parameters for count query (no limit/offset)
    count_params = params.copy()
    
    return select_sql, count_sql, select_params, count_params


@app.route('/api/express-search', methods=['POST'])
def api_express_search():
    """
    API endpoint for express modal search filtering.
    
    Accepts JSON body with filter parameters and returns matching listings.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False, 
                'error': 'Request body is required'
            }), 400
        
        # Validate property_type
        property_type = data.get('property_type', 'apartment')
        if property_type not in ('apartment', 'house', 'commercial'):
            return jsonify({
                'success': False, 
                'error': 'Invalid property type. Must be apartment, house, or commercial'
            }), 400
        
        # Validate listing_type
        listing_type = data.get('listing_type', 'for_sale')
        if listing_type not in ('for_sale', 'for_rent'):
            return jsonify({
                'success': False, 
                'error': 'Invalid listing type. Must be for_sale or for_rent'
            }), 400
        
        # Validate price range
        try:
            price_min = int(data.get('price_min', 0))
            price_max = int(data.get('price_max', 999999999))
            if price_min < 0 or price_max < 0:
                raise ValueError("Prices must be non-negative")
            if price_min > price_max:
                raise ValueError("price_min cannot exceed price_max")
        except (TypeError, ValueError) as e:
            return jsonify({
                'success': False, 
                'error': f'Invalid price range: {str(e)}'
            }), 400
        
        # Validate price per m² range
        try:
            price_m2_min = int(data.get('price_m2_min', 0))
            price_m2_max = int(data.get('price_m2_max', 999999))
            if price_m2_min < 0 or price_m2_max < 0:
                raise ValueError("Price per m² must be non-negative")
            if price_m2_min > price_m2_max:
                raise ValueError("price_m2_min cannot exceed price_m2_max")
        except (TypeError, ValueError) as e:
            price_m2_min = 0
            price_m2_max = 999999
        
        # Validate limit and offset
        try:
            limit = int(data.get('limit', 5))
            offset = int(data.get('offset', 0))
            if limit < 1 or limit > 100:
                limit = 5
            if offset < 0:
                offset = 0
        except (TypeError, ValueError):
            limit = 5
            offset = 0
        
        # Get features (optional)
        features = data.get('features', {})
        if not isinstance(features, dict):
            features = {}
        
        # Get amenities (optional)
        amenities = data.get('amenities', {})
        if not isinstance(amenities, dict):
            amenities = {}
        
        # Get location filter (optional)
        location = data.get('location', None)
        location_lat = None
        location_lng = None
        location_radius = 10  # Default 10km
        if location and isinstance(location, dict):
            try:
                location_lat = float(location.get('lat'))
                location_lng = float(location.get('lng'))
                location_radius = float(location.get('radius', 10))
            except (TypeError, ValueError):
                location_lat = None
                location_lng = None
        
        # Build filter dict
        filters = {
            'property_type': property_type,
            'listing_type': listing_type,
            'price_min': price_min,
            'price_max': price_max,
            'price_m2_min': price_m2_min,
            'price_m2_max': price_m2_max,
            'features': features,
            'amenities': amenities,
            'limit': limit,
            'offset': offset,
            'location_lat': location_lat,
            'location_lng': location_lng,
            'location_radius': location_radius
        }
        
        # Build and execute query
        select_sql, count_sql, select_params, count_params = build_express_query(filters)
        
        conn = get_db_connection("/api/express")
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute(count_sql, count_params)
        total_count = cursor.fetchone()[0]
        
        # Get listings
        cursor.execute(select_sql, select_params)
        rows = cursor.fetchall()
        
        listings = []
        for row in rows:
            listing_data = dict(row)
            
            # Parse price_json to get display price and numeric value
            display_price = "N/A"
            price_numeric = 0
            try:
                if listing_data['price_json']:
                    price_obj = json.loads(listing_data['price_json'])
                    if price_obj:
                        display_price = list(price_obj.values())[0]
                        # Extract numeric value
                        price_str = display_price.replace(',', '').replace(' ', '')
                        price_numeric = int(''.join(filter(str.isdigit, price_str)) or '0')
            except (json.JSONDecodeError, TypeError, IndexError, ValueError):
                pass
            
            listing_entry = {
                'id': listing_data['id'],
                'title_ro': listing_data['title_ro'],
                'title_ru': listing_data['title_ru'],
                'address': listing_data['address'],
                'display_price': display_price,
                'price_numeric': price_numeric,
                'surface_area': listing_data.get('surface_area'),
                'first_image': listing_data['first_image'],
                'property_type': listing_data['property_type'],
                'listing_type': listing_data['listing_type']
            }
            
            # Add coordinates for map display
            if listing_data.get('latitude') and listing_data.get('longitude'):
                listing_entry['lat'] = listing_data['latitude']
                listing_entry['lng'] = listing_data['longitude']
            
            # Add distance if location filter was used
            if 'distance_km' in listing_data.keys() and listing_data['distance_km'] is not None:
                listing_entry['distance_km'] = round(listing_data['distance_km'], 1)
            
            listings.append(listing_entry)
        
        # Get available feature values for all matching listings (for feature filter population)
        # This query gets distinct feature key-value pairs from listings matching the base filters
        # (property_type, listing_type, price_range) but NOT the feature filters themselves
        available_features = {}
        try:
            # Build base filter query (without feature filters) to get all matching listing IDs
            base_filters = {
                'property_type': property_type,
                'listing_type': listing_type,
                'price_min': price_min,
                'price_max': price_max,
                'features': {},  # No feature filters for this query
                'limit': 10000,  # High limit to get all
                'offset': 0
            }
            base_select_sql, _, base_params, _ = build_express_query(base_filters)
            
            # Query to get all distinct feature values from matching listings
            # Get Romanian features first (used as filter keys)
            features_sql = f"""
                SELECT DISTINCT lf_ro.feature_key, lf_ro.feature_value as value_ro
                FROM listing_features lf_ro
                WHERE lf_ro.listing_id IN (
                    SELECT DISTINCT l.id FROM listings l
                    WHERE l.status = 'active'
                    AND l.property_type = ?
                    AND l.listing_type = ?
                    AND CAST(
                        REPLACE(REPLACE(REPLACE(REPLACE(
                            SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                        ',', ''), ' ', ''), '€', ''), '"', '')
                    AS INTEGER) BETWEEN ? AND ?
                )
                AND lf_ro.lang = 'ro'
                AND lf_ro.feature_value IS NOT NULL
                AND lf_ro.feature_value != ''
                ORDER BY lf_ro.feature_key, lf_ro.feature_value
            """
            cursor.execute(features_sql, [property_type, listing_type, price_min, price_max])
            feature_rows = cursor.fetchall()
            
            # Build mapping of Romanian feature key -> Russian feature key
            from Helper.amenity_translations import FEATURES
            ro_to_ru_key = {}
            for eng_key, translations in FEATURES.items():
                ro_key = translations.get('ro', '')
                ru_key = translations.get('ru', '')
                if ro_key and ru_key:
                    ro_to_ru_key[ro_key] = ru_key
            
            # For each Romanian feature, try to find the Russian translation
            for frow in feature_rows:
                feature_key_ro = frow['feature_key']
                value_ro = frow['value_ro']
                
                # Try to get Russian value by querying with Russian feature key
                value_ru = value_ro  # Default fallback
                ru_feature_key = ro_to_ru_key.get(feature_key_ro)
                if ru_feature_key:
                    # Find a listing that has this Romanian value and get its Russian equivalent
                    ru_query = """
                        SELECT DISTINCT lf_ru.feature_value
                        FROM listing_features lf_ru
                        WHERE lf_ru.listing_id IN (
                            SELECT listing_id FROM listing_features 
                            WHERE lang = 'ro' AND feature_key = ? AND feature_value = ?
                        )
                        AND lf_ru.lang = 'ru'
                        AND lf_ru.feature_key = ?
                        LIMIT 1
                    """
                    cursor.execute(ru_query, [feature_key_ro, value_ro, ru_feature_key])
                    ru_row = cursor.fetchone()
                    if ru_row and ru_row['feature_value']:
                        value_ru = ru_row['feature_value']
                
                if feature_key_ro not in available_features:
                    available_features[feature_key_ro] = []
                # Store as object with both languages, using Romanian as the filter key
                feature_obj = {'ro': value_ro, 'ru': value_ru, 'key': value_ro}
                # Check if this value_ro already exists
                if not any(f['key'] == value_ro for f in available_features[feature_key_ro]):
                    available_features[feature_key_ro].append(feature_obj)
        except Exception as e:
            print(f"Error fetching available features: {e}")
            # Continue without available features on error
        
        # Get available amenities from matching listings
        available_amenities = []
        try:
            amenities_sql = f"""
                SELECT DISTINCT la.amenity_key
                FROM listing_amenities la
                WHERE la.listing_id IN (
                    SELECT DISTINCT l.id FROM listings l
                    WHERE l.status = 'active'
                    AND l.property_type = ?
                    AND l.listing_type = ?
                    AND CAST(
                        REPLACE(REPLACE(REPLACE(REPLACE(
                            SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                        ',', ''), ' ', ''), '€', ''), '"', '')
                    AS INTEGER) BETWEEN ? AND ?
                )
                AND la.lang = 'ro'
                ORDER BY la.amenity_key
            """
            cursor.execute(amenities_sql, [property_type, listing_type, price_min, price_max])
            amenity_rows = cursor.fetchall()
            available_amenities = [row['amenity_key'] for row in amenity_rows]
        except Exception as e:
            print(f"Error fetching available amenities: {e}")
            # Continue without available amenities on error
        
        # Get max price for this property type AND listing type (regardless of other filters)
        max_price_for_type = 1000000  # Default fallback
        min_price_for_type = 0  # Default fallback
        try:
            price_range_sql = """
                SELECT 
                    MIN(
                        CAST(
                            REPLACE(REPLACE(REPLACE(REPLACE(
                                SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                            ',', ''), ' ', ''), '€', ''), '"', '')
                        AS INTEGER)
                    ) as min_price,
                    MAX(
                        CAST(
                            REPLACE(REPLACE(REPLACE(REPLACE(
                                SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                            ',', ''), ' ', ''), '€', ''), '"', '')
                        AS INTEGER)
                    ) as max_price
                FROM listings l
                WHERE l.status = 'active'
                AND l.property_type = ?
                AND l.listing_type = ?
                AND CAST(
                    REPLACE(REPLACE(REPLACE(REPLACE(
                        SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                    ',', ''), ' ', ''), '€', ''), '"', '')
                AS INTEGER) > 0
            """
            cursor.execute(price_range_sql, [property_type, listing_type])
            price_row = cursor.fetchone()
            if price_row:
                if price_row['min_price'] is not None and price_row['min_price'] > 0:
                    min_price_for_type = price_row['min_price']
                if price_row['max_price'] is not None and price_row['max_price'] > 0:
                    max_price_for_type = price_row['max_price']
        except Exception as e:
            print(f"Error fetching price range: {e}")
        
        # Get price per m² range for this property type AND listing type
        max_price_m2_for_type = 5000  # Default fallback
        min_price_m2_for_type = 0  # Default fallback
        try:
            # Calculate price per m² from price and surface area
            price_m2_range_sql = """
                SELECT 
                    MIN(
                        CAST(
                            REPLACE(REPLACE(REPLACE(REPLACE(
                                SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                            ',', ''), ' ', ''), '€', ''), '"', '')
                        AS REAL)
                        /
                        CAST(lf.feature_value AS REAL)
                    ) as min_price_m2,
                    MAX(
                        CAST(
                            REPLACE(REPLACE(REPLACE(REPLACE(
                                SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                            ',', ''), ' ', ''), '€', ''), '"', '')
                        AS REAL)
                        /
                        CAST(lf.feature_value AS REAL)
                    ) as max_price_m2
                FROM listings l
                LEFT JOIN listing_features lf ON l.id = lf.listing_id 
                    AND lf.lang = 'ro' 
                    AND lf.feature_key = 'Suprafață totală'
                WHERE l.status = 'active'
                AND l.property_type = ?
                AND l.listing_type = ?
                AND lf.feature_value IS NOT NULL
                AND lf.feature_value != ''
                AND CAST(lf.feature_value AS REAL) > 0
                AND CAST(
                    REPLACE(REPLACE(REPLACE(REPLACE(
                        SUBSTR(l.price_json, INSTR(l.price_json, ': "') + 3),
                    ',', ''), ' ', ''), '€', ''), '"', '')
                AS REAL) > 0
            """
            cursor.execute(price_m2_range_sql, [property_type, listing_type])
            m2_row = cursor.fetchone()
            if m2_row:
                if m2_row['min_price_m2'] is not None and m2_row['min_price_m2'] > 0:
                    min_price_m2_for_type = int(m2_row['min_price_m2'])
                if m2_row['max_price_m2'] is not None and m2_row['max_price_m2'] > 0:
                    max_price_m2_for_type = int(m2_row['max_price_m2'])
        except Exception as e:
            print(f"Error fetching price per m² range: {e}")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_count': total_count,
            'listings': listings,
            'available_features': available_features,
            'available_amenities': available_amenities,
            'min_price_for_type': min_price_for_type,
            'max_price_for_type': max_price_for_type,
            'min_price_m2_for_type': min_price_m2_for_type,
            'max_price_m2_for_type': max_price_m2_for_type
        })
        
    except sqlite3.Error as e:
        print(f"Database error in express-search: {e}")
        return jsonify({
            'success': False, 
            'error': 'Database error'
        }), 500
    except Exception as e:
        print(f"Error in express-search: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Check if database exists
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        print("Please make sure Mainframe.db exists in the project directory.")
        exit(1)
    
    # Check if Listings directory exists
    if not LISTINGS_DIR.exists():
        print(f"⚠️  Warning: Listings directory not found at {LISTINGS_DIR}")
        print("Creating Listings directory...")
        LISTINGS_DIR.mkdir(exist_ok=True)
    
    # Get local network IP for smartphone access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"
    
    print("🏛️  RealAgent Dashboard")
    print(f"📊 http://localhost:5000")
    print(f"📊 http://127.0.0.1:5000 (use this for Safari)")
    print(f"📱 http://{local_ip}:5000 (for smartphones on same network)\n")
    
    # Run Flask app with minimal logging
    # Bind to 0.0.0.0 to allow access from other devices on the network
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(debug=False, host='0.0.0.0', port=5000)
