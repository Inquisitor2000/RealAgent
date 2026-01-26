"""
Scraper Wrapper for Dashboard Integration
==========================================

This module provides a wrapper around Agent.py functionality to allow
the dashboard to trigger scraping operations programmatically.
"""

import sys
import asyncio
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def scrape_listing_from_url(url: str, template_name: str = 'luna') -> dict:
    """
    Scrape a single listing from a URL and save it to the database.
    
    This function wraps the Agent.py scraping logic and makes it callable
    from the dashboard API.
    
    Args:
        url: The URL of the listing to scrape (e.g., 999.md listing)
        template_name: Template to use for HTML generation (default: 'luna')
        
    Returns:
        Dictionary with:
        - success: bool - Whether scraping succeeded
        - listing_id: str - ID of created listing (if successful)
        - error: str - Error message (if failed)
    """
    try:
        # Import Agent.py functions
        from Agent import fetch_listing_data, geocode_with_cache
        from Helper.database import save_listing_to_mainframe, init_mainframe_db
        from regenerate_html import regenerate_listing_by_id
        import re
        import urllib.parse
        
        # Extract listing ID from URL
        parsed = urllib.parse.urlparse(url)
        match = re.search(r'/(\d+)/?', parsed.path)
        if not match:
            return {
                'success': False,
                'error': 'Could not extract listing ID from URL'
            }
        
        listing_id = match.group(1)
        
        # Check if listing already exists
        conn = init_mainframe_db()
        c = conn.cursor()
        c.execute('SELECT id FROM listings WHERE id = ?', (listing_id,))
        existing = c.fetchone()
        conn.close()
        
        if existing:
            return {
                'success': False,
                'error': f'Listing {listing_id} already exists in database'
            }
        
        print(f"🔄 Scraping listing from: {url}")
        
        # Run async scraping
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Fetch listing data
            raw_data = loop.run_until_complete(fetch_listing_data(url))
            
            if not raw_data:
                return {
                    'success': False,
                    'error': 'Failed to fetch listing data'
                }
            
            # Determine language from URL
            provided_lang = 'ro' if '/ro/' in url else 'ru'
            other_lang = 'ru' if provided_lang == 'ro' else 'ro'
            
            # Create localized structure (Agent.py expects this format)
            localized = {
                provided_lang: {
                    'title': raw_data.get('title', ''),
                    'description': raw_data.get('description', ''),
                    'features': raw_data.get('features', {}),
                    'amenities': raw_data.get('amenities', {})
                }
            }
            
            # Try to fetch the other language version
            try:
                other_url = url.replace(f'/{provided_lang}/', f'/{other_lang}/')
                other_data = loop.run_until_complete(fetch_listing_data(other_url))
                
                if other_data:
                    localized[other_lang] = {
                        'title': other_data.get('title', ''),
                        'description': other_data.get('description', ''),
                        'features': other_data.get('features', {}),
                        'amenities': other_data.get('amenities', {})
                    }
                    print(f"✅ Fetched both {provided_lang.upper()} and {other_lang.upper()} versions")
                else:
                    # Fallback: copy primary language data
                    localized[other_lang] = localized[provided_lang].copy()
                    print(f"⚠️  Using {provided_lang.upper()} data for both languages")
            except Exception as e:
                # Fallback: copy primary language data
                localized[other_lang] = localized[provided_lang].copy()
                print(f"⚠️  Could not fetch {other_lang.upper()} version: {e}")
            
            # Prepare bilingual features and amenities from localized data
            # This matches how Agent.py processes the data before saving to Mainframe
            bilingual_features_dict = {'ro': {}, 'ru': {}}
            bilingual_amenities_dict = {'ro': {}, 'ru': {}}
            
            for lang_key in ['ro', 'ru']:
                if localized.get(lang_key):
                    # Features
                    lang_features = localized[lang_key].get('features', {})
                    bilingual_features_dict[lang_key] = lang_features if isinstance(lang_features, dict) else {}
                    
                    # Amenities
                    lang_amenities = localized[lang_key].get('amenities', {})
                    bilingual_amenities_dict[lang_key] = lang_amenities if isinstance(lang_amenities, dict) else {}
            
            # Build listing data in the format expected by save_listing_to_mainframe
            listing_data = {
                'id': listing_id,
                'url': url,
                'domain': '999.md',
                'title': localized[provided_lang]['title'],
                'description': localized[provided_lang]['description'],
                'price': raw_data.get('price', {}),
                'address': raw_data.get('address', ''),
                'contact': raw_data.get('contact', 'N/A'),
                'images': raw_data.get('images', []),
                'features': bilingual_features_dict,  # Bilingual format
                'amenities': bilingual_amenities_dict,  # Bilingual format
                'standard_features': raw_data.get('standard_features', {}),
                'localized': localized,
                'folder_path': f'Listings/{listing_id}',
                'template_name': template_name
            }
            
            # Copy extra address fields if present
            for key in ['display_address', 'geocoding_address', 'street_part', 'building_number', 'district']:
                if key in raw_data:
                    listing_data[key] = raw_data[key]
            
            # Geocode address if available
            if listing_data.get('address') and listing_data['address'] != 'N/A':
                display_address = listing_data.get('display_address', listing_data['address'])
                geocoding_address = listing_data.get('geocoding_address', listing_data['address'])
                
                # Import both cache and full geocoding functions
                from Agent import geocode_with_cache, geocode_address
                import re
                
                # Check if address has a building number (not just digits in postal code or district)
                # Look for digit followed by optional letter/slash (e.g., "15", "15A", "15/2")
                # Building number is in the FIRST part (street + number), not last part (country)
                # Format: "Strada Name 7, District, City, Moldova"
                address_first_part = geocoding_address.split(',')[0] if ',' in geocoding_address else geocoding_address
                has_building_number = bool(re.search(r'\b\d+[A-Za-z]?(/\d+)?\b', address_first_part))
                
                print(f"🔍 Address check: '{address_first_part.strip()}'")
                print(f"   Has building number: {has_building_number}")
                
                # Skip cache check - always perform fresh geocoding
                db_path = project_root / 'Mainframe.db'
                map_data = None
                
                if not has_building_number:
                    print("   ⚠️  No building number - will use full geocoding with confidence check")
                
                # Always perform fresh geocoding (cache disabled)
                if True:
                    print("   🌍 Running full geocoding with confidence scoring...")
                    
                    # If no building number, we need stricter validation
                    # Temporarily modify the geocoding to require higher confidence
                    if not has_building_number:
                        # For addresses without building numbers, always trigger map correction
                        # by using a custom wrapper that forces the interactive map
                        from Helper.map_overlay import create_interactive_map
                        
                        print("   ⚠️  Address missing building number - opening interactive map for verification...")
                        
                        # Try geocoding first to get estimated coordinates
                        # Skip the internal interactive map trigger since we'll handle it here
                        temp_result = loop.run_until_complete(
                            geocode_address(display_address, geocoding_address, skip_interactive_map=True)
                        )
                        
                        if temp_result:
                            # Always show map for verification when no building number
                            map_result = create_interactive_map(
                                geocoding_address,
                                temp_result['lat'],
                                temp_result['lng']
                            )
                            
                            if map_result:
                                # Unpack the tuple: (lat, lng, corrected_address)
                                corrected_lat, corrected_lng, corrected_address = map_result
                                
                                print(f"   ✅ User selected: {corrected_address}")
                                print(f"   📍 Coordinates: {corrected_lat}, {corrected_lng}")
                                
                                # Use the corrected coordinates and address
                                map_data = {
                                    'lat': corrected_lat,
                                    'lng': corrected_lng,
                                    'title': corrected_address,
                                    'corrected_address': corrected_address
                                }
                            else:
                                # User skipped - use original
                                map_data = temp_result
                        else:
                            # Geocoding failed completely
                            map_data = None
                    else:
                        # Normal geocoding with building number - will show interactive map if confidence is low
                        print("   🎯 Address has building number - geocoding...")
                        map_data = loop.run_until_complete(
                            geocode_address(display_address, geocoding_address)
                        )
                    
                    # Cache the result if successful
                    if map_data:
                        import sqlite3
                        import hashlib
                        from datetime import datetime, timezone
                        
                        # Generate cache key
                        def normalize_key(display, geocoding):
                            base = f"{display or ''}|{geocoding or ''}"
                            base = base.strip().lower()
                            base = __import__('re').sub(r'\s+', ' ', base)
                            return hashlib.sha1(base.encode('utf-8')).hexdigest() if base else None
                        
                        key = normalize_key(display_address, geocoding_address)
                        if key:
                            conn = sqlite3.connect(str(db_path))
                            try:
                                c = conn.cursor()
                                c.execute('INSERT OR REPLACE INTO geocode_cache (key, lat, lng, title, created_at) VALUES (?,?,?,?,?)',
                                          (key, map_data['lat'], map_data['lng'], map_data.get('title', display_address), 
                                           datetime.now(timezone.utc).isoformat()))
                                conn.commit()
                            finally:
                                conn.close()
                
                if map_data:
                    listing_data['map_data'] = map_data
                    print(f"✅ Geocoded address: {map_data['lat']}, {map_data['lng']}")
                    
                    # If user provided a corrected address, update all address-related fields
                    if map_data.get('corrected_address'):
                        corrected_addr = map_data['corrected_address']
                        print()  # Blank line for readability
                        
                        # Update main address fields
                        listing_data['address'] = corrected_addr
                        listing_data['display_address'] = corrected_addr
                        listing_data['geocoding_address'] = corrected_addr
                        
                        # Update map_data title
                        listing_data['map_data']['title'] = corrected_addr
                        
                        # CRITICAL: Update localized dictionary with corrected address
                        for lang_key in localized.keys():
                            if localized[lang_key]:
                                localized[lang_key]['address'] = corrected_addr
                        
                        # Mark as user-corrected
                        listing_data['user_corrected_address'] = True
                else:
                    print(f"⚠️  Geocoding failed for address: {display_address}")
            
            # Download images
            if listing_data.get('images'):
                from Agent import download_images_async
                
                listing_folder = project_root / 'Listings' / listing_id
                listing_folder.mkdir(parents=True, exist_ok=True)
                images_folder = listing_folder / 'images'
                images_folder.mkdir(exist_ok=True)
                
                # Keep original image URLs
                original_image_urls = listing_data['images'].copy()
                
                print(f"📥 Downloading {len(original_image_urls)} images...")
                local_images = loop.run_until_complete(
                    download_images_async(
                        original_image_urls, 
                        str(images_folder), 
                        str(listing_folder)
                    )
                )
                
                # Filter out None values (failed downloads)
                local_images = [img for img in local_images if img is not None]
                
                if local_images:
                    # Keep both original URLs and local paths
                    listing_data['images'] = original_image_urls
                    listing_data['local_images'] = local_images
                    print(f"✅ Downloaded {len(local_images)} images")
            
            # Save to database
            print(f"💾 Saving to database...")
            success = save_listing_to_mainframe(listing_data)
            
            if not success:
                return {
                    'success': False,
                    'error': 'Failed to save listing to database'
                }
            
            print(f"✅ Saved to database: {listing_id}")
            
            # Fetch and save POI data
            if listing_data.get('map_data') and listing_data['map_data'].get('lat') and listing_data['map_data'].get('lng'):
                try:
                    from Helper.poi_fetcher import fetch_pois_for_listing
                    from Helper.database import save_poi_data_to_mainframe
                    
                    lat = float(listing_data['map_data']['lat'])
                    lng = float(listing_data['map_data']['lng'])
                    
                    print(f"📍 Fetching POI data...")
                    poi_data, poi_summary = loop.run_until_complete(
                        fetch_pois_for_listing(lat, lng, radius=500)
                    )
                    
                    if poi_data:
                        # Show detailed breakdown before saving
                        print(f"\n📊 POI Fetch Summary:")
                        for category, pois in poi_data.items():
                            count = len(pois)
                            if count > 0:
                                print(f"   ✅ {category}: {count} POIs")
                            else:
                                print(f"   ⚠️  {category}: 0 POIs")
                        
                        poi_save_success = save_poi_data_to_mainframe(listing_id, poi_data, radius=500)
                        if poi_save_success:
                            total_pois = poi_summary.get('total_pois', 0)
                            categories = len(poi_summary.get('categories', {}))
                            print(f"\n✅ Successfully saved {total_pois} POIs across {categories} categories to database")
                        else:
                            print(f"\n⚠️  Failed to save POI data to database")
                    else:
                        print(f"⚠️  No POI data returned from fetch")
                except Exception as e:
                    print(f"⚠️  POI fetching failed: {e}")
            else:
                print("⚠️  No coordinates available - skipping POI data")
            
            # Generate HTML
            print(f"🎨 Generating HTML...")
            html_generated = False
            try:
                from Helper.builder import build_listing_html
                from pathlib import Path
                
                listing_folder = project_root / 'Listings' / listing_id
                html = build_listing_html(
                    listing_id=listing_id,
                    template_name=template_name,
                    base_url='',
                    save_to_file=True,
                    output_path=listing_folder / 'index.html'
                )
                
                if html:
                    print(f"✅ HTML generated successfully")
                    html_generated = True
                else:
                    print(f"⚠️  HTML generation failed")
            except Exception as e:
                print(f"⚠️  HTML generation error: {e}")
            
            # Generate PWA manifest
            pwa_generated = False
            try:
                from pwa.manifest_generator import create_pwa_manifest
                
                pwa_data = {
                    'id': listing_id,
                    'title': listing_data.get('title', 'Property Listing'),
                    'description': listing_data.get('description', 'Real estate property listing'),
                    'price': ' '.join(listing_data.get('price', {}).values()) if listing_data.get('price') else '',
                    'location': listing_data.get('address', ''),
                    'type': 'apartment',
                    'images': [os.path.basename(img) for img in listing_data.get('local_images', [])] if listing_data.get('local_images') else [],
                    'coordinates': [listing_data['map_data']['lat'], listing_data['map_data']['lng']] if listing_data.get('map_data') else None,
                    'phone': listing_data.get('contact', ''),
                    'timestamp': '',
                    'lang': provided_lang
                }
                
                listing_folder_str = str(project_root / 'Listings' / listing_id)
                manifest_path = create_pwa_manifest(pwa_data, listing_folder_str, '')
                print(f"✅ PWA manifest generated")
                pwa_generated = True
            except Exception as e:
                print(f"⚠️  PWA manifest generation failed: {e}")
            
            # Add journal entry
            from Helper.database import add_journal_entry
            add_journal_entry(
                title='scraped',
                content=f"Listing scraped from {url}",
                entry_type='log',
                listing_id=listing_id,
                user='Dashboard'
            )
            
            return {
                'success': True,
                'listing_id': listing_id,
                'processes_completed': {
                    'data_scraping': True,
                    'image_download': bool(listing_data.get('local_images')),
                    'database_save': True,
                    'poi_fetch': bool(poi_data),
                    'html_generation': html_generated,
                    'pwa_manifest': pwa_generated
                },
                'message': f'Successfully scraped and saved listing {listing_id}'
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        print(f"❌ Error scraping listing: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e)
        }


def scrape_multiple_listings(urls: list) -> dict:
    """
    Scrape multiple listings from a list of URLs.
    
    Args:
        urls: List of URLs to scrape
        
    Returns:
        Dictionary with:
        - success: int - Number of successful scrapes
        - failed: int - Number of failed scrapes
        - total: int - Total URLs processed
        - results: list - Individual results for each URL
    """
    results = []
    success_count = 0
    failed_count = 0
    
    for url in urls:
        result = scrape_listing_from_url(url)
        results.append({
            'url': url,
            'result': result
        })
        
        if result['success']:
            success_count += 1
        else:
            failed_count += 1
    
    return {
        'success': success_count,
        'failed': failed_count,
        'total': len(urls),
        'results': results
    }


if __name__ == '__main__':
    # CLI interface for testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape listings from URLs')
    parser.add_argument('url', help='URL of the listing to scrape')
    
    args = parser.parse_args()
    
    result = scrape_listing_from_url(args.url)
    
    if result['success']:
        print(f"\n✅ Success! Listing ID: {result['listing_id']}")
        sys.exit(0)
    else:
        print(f"\n❌ Failed: {result['error']}")
        sys.exit(1)
