import asyncio
import aiohttp
import os
import sys
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image
# Translation module for property features
from Helper.translations import PROPERTY_FEATURE_TRANSLATIONS, ROMANIAN_TO_RUSSIAN_FEATURES
# PWA manifest generation
sys.path.append(os.path.join(os.path.dirname(__file__), 'pwa'))
from manifest_generator import create_pwa_manifest
# Helper module for address parsing and geocoding
from Helper.geoguess import (
    detect_cyrillic_text,
    translate_russian_to_romanian,
    parse_address_string,
    build_geocode_queries,
    get_all_translations
)
# Helper module for Mainframe database
from Helper.database import save_listing_to_mainframe, get_listing_from_mainframe
# Guard async Playwright import; provide clean fallback when unavailable
try:
    from playwright.async_api import async_playwright  # type: ignore
except Exception:
    async_playwright = None  # Fallback path will be used

# Configuration
VERBOSE_GEOCODING = False  # Set to True for detailed geocoding logs

# Base URL for Open Graph and sharing - CHANGE THIS FOR PRODUCTION
BASE_URL = "https://192.168.0.3:8443"  # For local development
# BASE_URL = "https://yourdomain.com"  # For production hosting

# IMPORTANT: For share button to work with images on social media:
# 1. Images must be accessible from a PUBLIC URL (not localhost/local IP)
# 2. Comment out the localhost line above
# 3. Uncomment and modify the production line with your domain
# 4. Example: BASE_URL = "https://listings.mysite.com"
# 5. Deploy your generated folders to a web server accessible from the internet

def log_info(message):
    """Print important information messages."""
    print(f"ℹ️  {message}")

def log_success(message):
    """Print success messages."""
    print(f"✅ {message}")

def log_warning(message):
    """Print warning messages."""
    print(f"⚠️  {message}")

def log_verbose(message):
    """Print verbose messages only if VERBOSE_GEOCODING is True."""
    if VERBOSE_GEOCODING:
        print(f"🔍 {message}")

def clean_description_html(description):
    """Clean description HTML, convert <br> to newlines, preserve formatting."""
    import re
    from html import unescape
    
    if not description or description == "N/A":
        return "N/A"
    
    # Convert to string and decode HTML entities first
    html_content = str(description)
    html_content = unescape(html_content)
    
    # Remove script, style, and other dangerous tags completely
    html_content = re.sub(r'<(script|style|iframe|object|embed)[^>]*>.*?</\1>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
    
    # Convert <br> tags to actual newlines to preserve line formatting
    html_content = re.sub(r'<br[^>]*></br>', '\n', html_content, flags=re.IGNORECASE)  # Fix malformed <br></br>
    html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)  # Convert all <br> variants to \n
    
    # Convert block-level elements to newlines to preserve paragraph structure
    html_content = re.sub(r'</p>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</div>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</h[1-6]>', '\n', html_content, flags=re.IGNORECASE)
    
    # Remove unwanted tags but preserve their content
    unwanted_tags = ['a', 'span', 'font', 'center', 'table', 'tr', 'td', 'th', 'tbody', 'thead']
    for tag in unwanted_tags:
        html_content = re.sub(f'<{tag}[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(f'</{tag}>', '', html_content, flags=re.IGNORECASE)
    
    # Remove ALL remaining HTML tags (including any leftover formatting)
    html_content = re.sub(r'<[^>]+>', '', html_content)
    
    # Remove URLs (both http/https and www patterns)
    html_content = re.sub(r'https?://[^\s<>"]+', '', html_content)
    html_content = re.sub(r'www\.[^\s<>"]+', '', html_content)
    
    # Clean up whitespace while preserving intentional line breaks
    html_content = re.sub(r'[ \t]+', ' ', html_content)  # Normalize horizontal whitespace
    html_content = re.sub(r' *\n *', '\n', html_content)  # Clean spaces around newlines
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)  # Limit to max 2 consecutive newlines
    
    # Trim leading and trailing whitespace
    html_content = html_content.strip()
    
    # Final cleanup - remove any empty or whitespace-only content
    if not html_content or html_content.isspace():
        return "N/A"
    
    return html_content

def sanitize_description_for_meta(description):
    """Sanitize description for use in meta tags by removing HTML and links."""
    import re
    from html import unescape
    
    if not description or description == "N/A":
        return ""
    
    # Remove HTML tags
    clean_desc = re.sub(r'<[^>]+>', ' ', description)
    
    # Remove URLs (both http/https and www patterns)
    clean_desc = re.sub(r'https?://[^\s<>"]+', '', clean_desc)
    clean_desc = re.sub(r'www\.[^\s<>"]+', '', clean_desc)
    
    # Decode HTML entities
    clean_desc = unescape(clean_desc)
    
    # Normalize whitespace
    clean_desc = re.sub(r'\s+', ' ', clean_desc)
    
    # Trim and limit length for meta tags (recommended max 160 chars for description)
    clean_desc = clean_desc.strip()
    if len(clean_desc) > 160:
        clean_desc = clean_desc[:157] + "..."
    
    return clean_desc

def prompt_user_for_address_correction(display_address, geocoding_address, best_result, confidence_score):
    """Automatically open interactive map when geocoding confidence is low."""
    print(f"\n🗺️  Low geocoding confidence (Score: {confidence_score}/100) - Opening map...")
    
    try:
        from Helper.map_overlay import create_interactive_map
        
        # Use best result coordinates if available, otherwise default to Chișinău
        estimated_lat = 47.0105  # Default Chișinău center
        estimated_lng = 28.8638
        
        if best_result and 'lat' in best_result and 'lon' in best_result:
            estimated_lat = float(best_result['lat'])
            estimated_lng = float(best_result['lon'])
        
        map_result = create_interactive_map(display_address, estimated_lat, estimated_lng)
        
        if map_result:
            lat, lng, corrected_address = map_result
            return corrected_address
        else:
            print("❌  Map selection cancelled.")
            return None
            
    except ImportError:
        print("❌  Map overlay module not available. Install: pip install folium")
        return None
    except Exception as e:
        print(f"❌  Error opening map: {e}")
        return None

# --- Async Geocoding ---
async def geocode_address(display_address, geocoding_address, retry_attempt=False, skip_interactive_map=False):
    """Geocode an address using a multi-service, prioritized strategy.
    
    Scoring system (max 100 points):
    - City: 25 points
    - Street: 40 points
    - House number: 35 points
    
    Confidence levels:
    - High (>=90): Accept immediately (nearly perfect match)
    - Medium/Low (<90): Prompt user for interactive map correction
    
    Args:
        display_address: Human-readable address for display
        geocoding_address: Cleaned address for geocoding
        retry_attempt: Whether this is a retry with corrected address
        skip_interactive_map: (Deprecated) Skip interactive map prompt - kept for compatibility
    """
    if not geocoding_address or geocoding_address == "N/A":
        return None

    # For retry attempts with corrected address, skip translation and use address as-is
    if retry_attempt:
        # Parse the corrected address to extract street/building/district for fallback methods
        parsed = parse_address_string(geocoding_address)
        # Mark as user-corrected
        parsed['corrected_by_user'] = True
        parsed['display_address'] = geocoding_address
        parsed['geocoding_address'] = geocoding_address
        # Build queries from the parsed corrected address
        queries = build_geocode_queries(parsed, geocoding_address)
        # Use corrected address as the display title for Leaflet marker
        display_title = geocoding_address
    else:
        parsed = parse_address_string(display_address, show_table=False)
        queries = build_geocode_queries(parsed, geocoding_address)
        # Use the display address as-is (no translation)
        display_title = display_address

    async with aiohttp.ClientSession() as session:
        best_overall_result = None
        best_overall_score = -1
        
        # Show progress indicator
        import sys
        progress_chars = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']  # Taller/fuller spinner characters
        progress_idx = 0
        
        print("🔍  Searching address", end="", flush=True)
        
        for i, query in enumerate(queries):
            log_verbose(f"Attempting geocode query {i+1}/{len(queries)}: '{query}'")
            
            # Show progress animation every 0.5 seconds during query
            import asyncio
            import time
            
            async def update_progress():
                nonlocal progress_idx
                while True:
                    print(f"\r🔍  Searching address {progress_chars[progress_idx % len(progress_chars)]}", end="", flush=True)
                    progress_idx += 1
                    await asyncio.sleep(0.5)
            
            # Start progress animation
            progress_task = asyncio.create_task(update_progress())
            
            try:
                results = await query_geocoding_services_async(session, query)
            finally:
                # Stop progress animation
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

            if results:
                # Phase control: first 5 attempts favor detected city; afterwards favor default city (Chișinău)
                parsed['_city_mode'] = 'detected' if i < 5 else 'default'
                best_result, best_score = score_and_select_best(results, parsed)
                if best_result:
                    log_verbose(f"Best geocoding result found: {best_result['display_name']} (Score: {best_score})")
                    
                    # Track the best overall result
                    if best_score > best_overall_score:
                        best_overall_result = best_result
                        best_overall_score = best_score
                        # Simplified progress indicator
                        if VERBOSE_GEOCODING:
                            print(f"\r🎯  Better result found: {best_result.get('lat', 'N/A'):.6f}, {best_result.get('lon', 'N/A'):.6f} (Score: {best_score})                    ")
                            print("🔍  Searching address", end="", flush=True)
                    
                    # Accept good matches immediately (city + street = 65+ points)
                    if best_score >= 65:
                        # Stop progress animation and clear line
                        print("\r" + " " * 50 + "\r", end="", flush=True)  # Clear progress line
                        
                        # Extract city, street, and building from the best result
                        display_name = best_result.get('display_name', '')
                        address_parts = display_name.split(', ')
                        
                        # Try to extract meaningful parts (building, street, city)
                        building_part = address_parts[0] if address_parts else ''
                        street_part = address_parts[1] if len(address_parts) > 1 else ''
                        city_part = None
                        
                        # Find city (usually contains "Chișinău" or similar)
                        for part in address_parts:
                            if any(city in part.lower() for city in ['chișinău', 'chisinau', 'bălți', 'balti']):
                                city_part = part
                                break
                        
                        # Format the message
                        if city_part and street_part and building_part:
                            print(f"🏠 Address found: {city_part}, {street_part}, {building_part}.")
                        elif parsed.get('building'):
                            print(f"🏠 Address found for building {parsed.get('building')}.")
                        else:
                            print("🔍 Address found.")
                        # Show address table only in verbose mode
                        if not retry_attempt and VERBOSE_GEOCODING:
                            parse_address_string(display_address, show_table=True)
                        return {"lat": best_result["lat"], "lng": best_result["lon"], "title": display_title}
        
        # print("\r🔍  Address search completed          ")  # Clear progress line
        
        # Threshold system for address correction
        # Trigger interactive map correction for scores below 90 (medium/low confidence)
        needs_correction = False
        
        if best_overall_result:
            if best_overall_score < 90:  # Below 90 - offer map correction
                needs_correction = True
            else:
                # Excellent match (>=90) - accept it
                print()  # New line to clear progress indicator
                log_info(f"📍 Excellent geocoding match (Score: {best_overall_score}/100)")
        
        if needs_correction:
            # Prompt user for address correction (skip if this is already a retry OR if skip_interactive_map=True)
            if not retry_attempt and not skip_interactive_map:
                corrected_address = prompt_user_for_address_correction(display_address, geocoding_address, best_overall_result, best_overall_score)
                if corrected_address and corrected_address != geocoding_address:
                    # Recursive call with retry flag to prevent infinite loops
                    retry_result = await geocode_address(display_address, corrected_address, retry_attempt=True)
                    if retry_result:
                        # Include the corrected address in the result
                        retry_result['corrected_address'] = corrected_address
                        return retry_result
                    else:
                        log_warning("❌ Corrected address also failed geocoding. Using original result.")
                else:
                    log_info("📍 User skipped address correction. Using original result.")
            elif skip_interactive_map:
                # Address has building number - trust geocoding result even if low confidence
                log_info(f"📍 Address has building number - accepting geocoding result (Score: {best_overall_score}/100)")
        
        # Return best result found, even if low confidence
        if best_overall_result:
            # Clear progress indicator
            print("\r" + " " * 50 + "\r", end="", flush=True)
            
            # Always show geocoding confidence score with improved messaging
            if best_overall_score >= 90:
                log_success(f"📍 Geocoding completed - Excellent match (Score: {best_overall_score}/100)")
            elif best_overall_score >= 65:
                log_success(f"📍 Geocoding completed - Good match (Score: {best_overall_score}/100)")
            elif best_overall_score >= 45:
                log_info(f"📍 Geocoding completed - Acceptable match (Score: {best_overall_score}/100)")
            else:
                log_warning(f"📍 Geocoding completed - Low confidence (Score: {best_overall_score}/100)")
            return {"lat": best_overall_result["lat"], "lng": best_overall_result["lon"], "title": display_title}
        
    log_warning("All geocoding attempts failed.")
    return None

async def query_geocoding_services_async(session, query):
    """Query Nominatim and Photon asynchronously, return combined results."""
    tasks = [
        asyncio.create_task(query_nominatim_async(session, query)),
        asyncio.create_task(query_photon_async(session, query))
    ]
    results = []
    for task in asyncio.as_completed(tasks):
        res = await task
        if res:
            results.extend(res)
    return results

async def query_nominatim_async(session, query):
    """Asynchronously query Nominatim with retries."""
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=5&countrycodes=md&addressdetails=1"
    try:
        response = await aiohttp_request_with_retries(
            session, url, headers={'User-Agent': 'RealAgent/1.0'}, timeout=10
        )
        if response is None:
            return []
        data = await response.json()
        return [{
            'lat': float(item.get('lat', 0)),
            'lon': float(item.get('lon', 0)),
            'display_name': item.get('display_name', ''),
            'type': item.get('type', ''),
            'class': item.get('class', ''),
            'service': 'nominatim'
        } for item in data]
    except Exception as e:
        print(f"Nominatim query failed: {e}")
        return []

async def query_photon_async(session, query):
    """Asynchronously query Photon with retries."""
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=5&bbox=28.6,46.8,29.2,47.2"
    try:
        response = await aiohttp_request_with_retries(session, url, timeout=10)
        if response is None:
            return []
        data = await response.json()
        if data.get('features'):
            return [{
                'lat': f['geometry']['coordinates'][1],
                'lon': f['geometry']['coordinates'][0],
                'display_name': f['properties'].get('name', '') + (', ' + f['properties'].get('street', '') if f['properties'].get('street') else ''),
                'type': f['properties'].get('osm_value', ''),
                'class': f['properties'].get('osm_key', ''),
                'service': 'photon'
            } for f in data['features']]
    except Exception as e:
        print(f"Photon query failed: {e}")
    return []


def map_scraped_features_to_standard(features_data, source_lang='ro'):
    """Map scraped features from 999.md to our standardized feature set"""
    
    # Standard feature mapping for both languages
    feature_mappings = {
        'ro': {
            # Ready to move
            'ready_to_move': ['gata de mutat', 'gata pentru mutare', 'gata de locuit'],
            
            # Building features
            'annex': ['anexă', 'anex', 'pристройка'],
            'terrace': ['terasă', 'terasa'],
            'separate_entrance': ['intrare separată', 'intrare independentă'],
            'park_area': ['zonă cu parc', 'parc în apropiere', 'zonă verde'],
            
            # Interior features
            'furnished': ['mobilat', 'mobilată', 'cu mobilă', 'mobilier inclus'],
            'appliances': ['cu tehnică electrocasnică', 'electrocasnice', 'cu aparate', 'tehnică inclusă'],
            
            # Heating & Climate
            'autonomous_heating': ['încălzire autonomă', 'căldură autonomă', 'încălzire independentă'],
            'air_conditioning': ['aer condiționat', 'climatizare', 'AC', 'aparat de aer'],
            'floor_heating': ['încălzire în pardoseală', 'pardoseală caldă', 'încălzire prin pardoseală'],
            
            # Windows & Doors
            'double_glazed_windows': ['termopan', 'geamuri termopan', 'ferestre termopan'],
            'panoramic_windows': ['geamuri panoramice', 'ferestre panoramice'],
            'armored_door': ['ușă blindată', 'ușă metalică', 'ușă de securitate'],
            
            # Flooring
            'parquet': ['parchet'],
            'laminate': ['laminat'],
            
            # Communication & Security
            'phone_line': ['linie telefonică', 'telefon fix'],
            'smart_home': ['sistem casă inteligentă', 'smart home', 'automatizare'],
            'intercom': ['interfon'],
            'internet': ['internet', 'conexiune internet'],
            'cable_tv': ['cablu tv', 'televiziune prin cablu', 'tv prin cablu'],
            'alarm_system': ['sistem de alarmă', 'alarmă', 'securitate'],
            'video_surveillance': ['supraveghere video', 'camere de supraveghere'],
            
            # Building amenities
            'elevator': ['ascensor', 'lift'],
            'playground': ['teren de joacă', 'loc de joacă pentru copii']
        },
        'ru': {
            # Ready to move
            'ready_to_move': ['готова к въезду', 'готова для проживания', 'готова к заселению'],
            
            # Building features
            'annex': ['пристройка', 'пристрой'],
            'terrace': ['терраса'],
            'separate_entrance': ['отдельный вход', 'независимый вход'],
            'park_area': ['парковая зона', 'рядом парк', 'зеленая зона'],
            
            # Interior features
            'furnished': ['меблирована', 'с мебелью', 'мебель включена'],
            'appliances': ['с бытовой техникой', 'с техникой', 'техника включена'],
            
            # Heating & Climate
            'autonomous_heating': ['автономное отопление', 'независимое отопление'],
            'air_conditioning': ['кондиционер', 'кондиционирование', 'климат-контроль'],
            'floor_heating': ['теплые полы', 'подогрев пола', 'напольное отопление'],
            
            # Windows & Doors
            'double_glazed_windows': ['стеклопакет', 'стеклопакеты', 'пластиковые окна'],
            'panoramic_windows': ['панорамные окна', 'большие окна'],
            'armored_door': ['бронированная дверь', 'металлическая дверь', 'дверь безопасности'],
            
            # Flooring
            'parquet': ['паркет'],
            'laminate': ['ламинат'],
            
            # Communication & Security
            'phone_line': ['телефонная линия', 'стационарный телефон'],
            'smart_home': ['система умный дом', 'умный дом', 'автоматизация'],
            'intercom': ['домофон'],
            'internet': ['интернет', 'интернет-соединение'],
            'cable_tv': ['тв кабель', 'кабельное тв', 'телевидение'],
            'alarm_system': ['сигнализация', 'система безопасности'],
            'video_surveillance': ['видеонаблюдение', 'камеры наблюдения'],
            
            # Building amenities
            'elevator': ['лифт'],
            'playground': ['детская площадка', 'игровая площадка']
        }
    }
    
    # Get the appropriate mapping for the source language
    mappings = feature_mappings.get(source_lang, feature_mappings['ro'])
    
    # Initialize standard features (all False by default)
    standard_features = {
        'ready_to_move': False,
        'annex': False,
        'terrace': False,
        'separate_entrance': False,
        'park_area': False,
        'furnished': False,
        'appliances': False,
        'autonomous_heating': False,
        'air_conditioning': False,
        'floor_heating': False,
        'double_glazed_windows': False,
        'panoramic_windows': False,
        'parquet': False,
        'laminate': False,
        'armored_door': False,
        'phone_line': False,
        'smart_home': False,
        'intercom': False,
        'internet': False,
        'cable_tv': False,
        'alarm_system': False,
        'video_surveillance': False,
        'elevator': False,
        'playground': False
    }
    
    # Convert features data to searchable text
    features_text = ''
    if isinstance(features_data, dict):
        for section, items in features_data.items():
            features_text += f' {section} '
            if isinstance(items, dict):
                for key, value in items.items():
                    features_text += f' {key} {value} '
            elif isinstance(items, list):
                for item in items:
                    features_text += f' {item} '
            else:
                features_text += f' {items} '
    
    features_text = features_text.lower()
    
    # Map scraped features to standard features
    for feature_key, search_terms in mappings.items():
        if feature_key in standard_features:
            for term in search_terms:
                if term.lower() in features_text:
                    standard_features[feature_key] = True
                    log_verbose(f"Mapped feature: '{term}' → {feature_key}")
                    break
    
    return standard_features

def translate_features_to_other_language(features_data, from_lang, to_lang):
    """Translate features using translations.py module"""
    import unicodedata
    
    if not features_data or not isinstance(features_data, dict):
        return {}
    
    # Use translations from translations.py module
    # PROPERTY_FEATURE_TRANSLATIONS is Russian -> Romanian
    # ROMANIAN_TO_RUSSIAN_FEATURES is Romanian -> Russian
    
    def _normalize_text(s):
        """Normalize text for case-insensitive, diacritic-aware exact matching"""
        if s is None:
            return ""
        # Normalize Unicode to NFC form
        s = unicodedata.normalize('NFC', str(s).strip())
        # Unify Romanian cedilla to comma diacritics (commonly seen variants)
        s = s.replace('ş', 'ș').replace('Ş', 'Ș').replace('ţ', 'ț').replace('Ţ', 'Ț')
        return s.lower()
    
    # Build case-insensitive, diacritic-normalized translation maps
    translation_maps_ci = {
        'ru_to_ro': {_normalize_text(k): v for k, v in PROPERTY_FEATURE_TRANSLATIONS.items()},
        'ro_to_ru': {_normalize_text(k): v for k, v in ROMANIAN_TO_RUSSIAN_FEATURES.items()}
    }
    
    def translate_text(text, from_lang, to_lang):
        """Translate a single text using our feature mappings"""
        if from_lang == to_lang:
            return text
            
        translation_key = f"{from_lang}_to_{to_lang}"
        tmap = translation_maps_ci.get(translation_key)
        if not tmap:
            return text
            
        # Normalize input text for case-insensitive, diacritic-aware lookup
        normalized_key = _normalize_text(text)
        
        # ONLY use exact match (on normalized form) to prevent mix-ups
        # Partial matching was causing values to get confused with keys
        if normalized_key in tmap:
            return tmap[normalized_key]
                
        # If no exact match found, return original text unchanged
        return text
    
    # Translate the features dictionary
    translated_features = {}
    
    for section, items in features_data.items():
        # Translate section name
        translated_section = translate_text(section, from_lang, to_lang)
        
        if isinstance(items, dict):
            translated_items = {}
            for key, value in items.items():
                translated_key = translate_text(key, from_lang, to_lang)
                translated_value = translate_text(value, from_lang, to_lang)
                translated_items[translated_key] = translated_value
            translated_features[translated_section] = translated_items
        elif isinstance(items, list):
            translated_items = []
            for item in items:
                translated_item = translate_text(item, from_lang, to_lang)
                translated_items.append(translated_item)
            translated_features[translated_section] = translated_items
        else:
            translated_item = translate_text(items, from_lang, to_lang)
            translated_features[translated_section] = translated_item
                
    return translated_features

def create_bilingual_features(features_data, source_lang):
    """Create features in both Romanian and Russian languages"""
    bilingual_features = {
        'ro': {},
        'ru': {}
    }
    
    if source_lang == 'ro':
        # Source is Romanian, translate to Russian
        bilingual_features['ro'] = features_data
        bilingual_features['ru'] = translate_features_to_other_language(features_data, 'ro', 'ru')
    elif source_lang == 'ru':
        # Source is Russian, translate to Romanian
        bilingual_features['ru'] = features_data
        bilingual_features['ro'] = translate_features_to_other_language(features_data, 'ru', 'ro')
    else:
        # Default to Romanian if language unclear
        bilingual_features['ro'] = features_data
        bilingual_features['ru'] = translate_features_to_other_language(features_data, 'ro', 'ru')
    
    log_verbose(f"Created bilingual features: RO={len(bilingual_features['ro'])} sections, RU={len(bilingual_features['ru'])} sections")
    return bilingual_features


def query_geocoding_services(query):
    """Query Nominatim and Photon, return combined results."""
    results = []
    # Nominatim
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=5&countrycodes=md&addressdetails=1"
        res = requests.get(url, headers={'User-Agent': 'RealAgent/1.0'}, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data:
            for item in data:
                results.append({
                    'lat': float(item.get('lat', 0)),
                    'lon': float(item.get('lon', 0)),
                    'display_name': item.get('display_name', ''),
                    'type': item.get('type', ''),
                    'class': item.get('class', ''),
                    'service': 'nominatim'
                })
    except Exception as e:
        print(f"Nominatim query failed: {e}")

    # Photon
    try:
        url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=5&bbox=28.6,46.8,29.2,47.2"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get('features'):
            for f in data['features']:
                props = f.get('properties', {})
                coords = f.get('geometry', {}).get('coordinates', [0, 0])
                results.append({
                    'lat': coords[1],
                    'lon': coords[0],
                    'display_name': props.get('name', '') + (', ' + props.get('street', '') if props.get('street') else ''),
                    'type': props.get('osm_value', ''),
                    'class': props.get('osm_key', ''),
                    'service': 'photon'
                })
    except Exception as e:
        print(f"Photon query failed: {e}")
        
    return results

def prioritize_coordinates_by_location_type(results, parsed):
    """Prioritize coordinates based on Building > City > District > Street hierarchy.
    
    Returns the best coordinate based on location type priority:
    1. Building/House-level coordinates (highest priority - specific address)
    2. City-level coordinates (high priority)
    3. District-level coordinates (medium priority) 
    4. Street-level coordinates (lowest priority)
    """
    building_results = []
    city_results = []
    district_results = []
    street_results = []
    
    # Detect target city from the original address directly
    detected_city = None
    try:
        # Define Moldovan cities directly
        city_names = ['chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat', 'кишинэу', 'кишинев']
        original_addr = (parsed.get('original_address') or '').lower()
        for cname in city_names:
            if cname and cname in original_addr:
                detected_city = cname
                break
        # Normalize common ASCII variant
        if not detected_city and 'chisinau' in original_addr:
            detected_city = 'chișinău'
    except Exception:
        detected_city = None

    # Override to default city in default mode
    mode = parsed.get('_city_mode')
    if mode == 'default':
        detected_city = 'chișinău'

    for res in results:
        name = res.get('display_name', '').lower()
        res_type = res.get('type', '').lower()
        res_class = res.get('class', '').lower()
        
        # Check if this result has address details with house number
        address_details = res.get('address', {})
        has_house_number = bool(address_details.get('house_number'))
        
        # Enhanced building detection - also check if building number appears in display_name
        building_number = parsed.get('building', '')
        has_building_in_name = building_number and building_number in res.get('display_name', '')
        
        # Classify result by location type (highest priority first)
        if (
            # Building/House level - highest priority for specific addresses
            (res_type in ['house', 'apartments', 'building', 'residential'] or res_class in ['building', 'place'])
            and (has_house_number or has_building_in_name)  # Accept if either condition is met
            and parsed.get('building')  # Only if we're looking for a specific building
        ):
            building_results.append(res)
        elif (
            res_type in ['city', 'town', 'municipality']
            or (res_class in ['place', 'boundary'] and (detected_city and detected_city in name))
        ):
            city_results.append(res)
        elif parsed.get('district') and parsed.get('district').lower() in name and res_type in ['suburb', 'neighbourhood', 'quarter', 'district']:
            district_results.append(res)
        elif parsed.get('street_name') and parsed.get('street_name').lower() in name:
            street_results.append(res)
    
    # Return results in priority order: Building > City > District > Street
    if building_results:
        best_building = max(building_results, key=lambda x: score_result(x, parsed))
        return best_building
    elif city_results:
        return max(city_results, key=lambda x: score_result(x, parsed))
    elif district_results:
        return max(district_results, key=lambda x: score_result(x, parsed))
    elif street_results:
        return max(street_results, key=lambda x: score_result(x, parsed))
    
    # Fallback to original scoring if no clear type match
    return None

def score_result(res, parsed):
    """Score a single geocoding result with clear priority: City (25) > Street (40) > House Number (35).
    
    Maximum score: 100 points
    - Correct city: 25 points
    - Correct street: 40 points  
    - Correct house number: 35 points
    
    Note: Results are pre-filtered by city in score_and_select_best(), so this function
    scores within the context of the already-identified city. This ensures hierarchical
    search: City first, then Street within that city, then House on that street.
    """
    score = 0
    name = res.get('display_name', '').lower()
    
    # Extract city from original address for dynamic prioritization
    original_addr = parsed.get('original_address', '').lower()
    city_from_address = None
    # Define Moldovan cities directly
    city_names = {'chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat', 'cricova', 'durlești', 'codru', 'кишинэу', 'кишинев'}

    for city in city_names:
        if city in original_addr:
            city_from_address = city
            break

    # Override city target if we are in default mode (force Chișinău)
    mode = parsed.get('_city_mode')
    if mode == 'default':
        city_from_address = 'chișinău'

    # 1. CITY SCORING (25 points max)
    if city_from_address:
        if city_from_address in name:
            score += 25  # Correct city match
        else:
            # Check if result is from a different city - heavy penalty
            for other_city in city_names:
                if other_city != city_from_address and other_city in name:
                    score -= 100  # Heavy penalty for wrong city
                    return score  # Return immediately - wrong city is unacceptable
    
    # 2. STREET SCORING (40 points max)
    street_name = parsed.get('street_name', '')
    if street_name and street_name.lower() in name:
        score += 40  # Correct street match
    
    # 2.5. DISTRICT SCORING (20 points bonus for district match, -50 penalty for wrong district)
    district = parsed.get('district', '')
    if district:
        district_lower = district.lower()
        # Check for district match
        if district_lower in name:
            score += 20  # Bonus for correct district
        else:
            # Check if result is from a different known district - penalty
            known_districts = ['botanica', 'centru', 'ciocana', 'râșcani', 'rîșcani', 'buiucani', 'telecentru', 'durlești', 'codru', 'sîngera', 'singera']
            for other_district in known_districts:
                if other_district != district_lower and other_district in name:
                    score -= 50  # Heavy penalty for wrong district
                    if VERBOSE_GEOCODING:
                        print(f"⚠️  District mismatch: Expected '{district}', found '{other_district}' (Score: -{50})")
                    break
    
    # 3. HOUSE NUMBER SCORING (35 points max)
    building = parsed.get('building', '')
    if building and building.lower() in name:
        score += 35  # Correct house number match
    
    # BONUS: Type-based validation (helps distinguish exact building from just street)
    res_type = res.get('type', '').lower()
    res_class = res.get('class', '').lower()
    address_details = res.get('address', {})
    has_house_number = bool(address_details.get('house_number'))
    
    # If we have a building number in address, prioritize building-level results
    if building:
        # Enhanced building detection - check both house_number field and building in display_name
        has_building_in_name = building and building in res.get('display_name', '')
        
        if (res_type in ['house', 'apartments', 'building', 'residential'] or res_class in ['building', 'place']) and (has_house_number or has_building_in_name):
            # MASSIVE bonus for building-level results (ensures they always win over city/street results)
            score += 40
        elif res_type in ['road', 'residential', 'street'] or res_class == 'highway':
            # Penalty if we got a street when we expected a building
            score -= 15
    
    # Ensure score doesn't exceed 100
    return min(score, 100)

def score_and_select_best(results, parsed):
    """Score results and return (best_result, best_score) with strict city-first hierarchy.
    
    Hierarchical search priority:
    1. Find the correct city from the address
    2. Filter ALL results to only include that city
    3. Within that city, search for the street
    4. Within that street, search for the house number
    
    This prevents ambiguity when different cities have streets with the same name.
    """
    # STRICT CITY FILTERING: Only consider results from the target city
    working_results = results
    target_city = None
    
    try:
        # Define Moldovan cities directly
        city_names = {'chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat', 'кишинэу', 'кишинев'}
        original_addr = (parsed.get('original_address') or '').lower()
        detected_city = None
        
        # Detect city from address
        for cname in city_names:
            if cname and cname in original_addr:
                detected_city = cname
                break
        if not detected_city and 'chisinau' in original_addr:
            detected_city = 'chișinău'
            
        # Override target city in default mode
        mode = parsed.get('_city_mode')
        target_city = 'chișinău' if mode == 'default' else detected_city
        
        # CRITICAL: Filter to ONLY results within the target city
        if target_city:
            city_filtered = [r for r in results if target_city in (r.get('display_name','').lower())]
            if city_filtered:
                working_results = city_filtered
                log_verbose(f"Filtered to {len(city_filtered)} results within {target_city.title()}")
            else:
                # No results in target city - this is a problem
                log_verbose(f"⚠️  No results found in target city {target_city.title()}")
                # Still try to filter out results from OTHER known cities
                non_other_cities = []
                for r in results:
                    display = r.get('display_name', '').lower()
                    is_other_city = False
                    for other_city in city_names:
                        if other_city != target_city and other_city in display:
                            is_other_city = True
                            break
                    if not is_other_city:
                        non_other_cities.append(r)
                if non_other_cities:
                    working_results = non_other_cities
    except Exception as e:
        log_verbose(f"City filtering error: {e}")

    # First try coordinate prioritization by location type
    prioritized_result = prioritize_coordinates_by_location_type(working_results, parsed)
    if prioritized_result:
        score = score_result(prioritized_result, parsed)
        prioritized_result['score'] = score
        log_verbose(f"Using prioritized coordinate: {prioritized_result.get('display_name')} (Type: {prioritized_result.get('type')})")
        return prioritized_result, score
    
    # Fallback to original scoring logic
    eligible = []
    best_any = None
    best_any_score = -1
    for res in working_results:
        score = score_result(res, parsed)
        res['score'] = score
        if score > 20:  # Low-confidence filter for eligible set
            eligible.append(res)
        # Track best regardless of threshold
        if score > best_any_score:
            best_any = res
            best_any_score = score
            
    if eligible:
        best = max(eligible, key=lambda x: x['score'])
        return best, best['score']
    # No eligible results — return best of all with its score (may be <= 20)
    return best_any, (best_any['score'] if best_any else -1)

# Additional imports for main functionality
import re
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
import urllib.parse
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Warning: PIL (Pillow) not found. Install with: pip install Pillow")
    Image = None
    ImageDraw = None
    ImageFont = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Warning: Playwright not found. Install with: pip install playwright")
    print("After installation, run: playwright install")
    sync_playwright = None


# Directory where you place your HTML templates
TEMPLATES_DIR = 'Templates'
# Will be set in main() to the full path of the chosen template
TEMPLATE_PATH = None

# --- Geocoding ---
# Preview creation removed - using original images directly

# --- Fetching with Playwright to reveal phone numbers ---
async def get_html_with_revealed_phone(url, browser=None):
    """Use Playwright to click 'Show Number' button and get full HTML.
    Returns None if Playwright is unavailable so caller can fallback cleanly.
    If browser is provided, uses it; otherwise creates a new one."""
    if not async_playwright:
        log_verbose("Playwright not available, falling back to requests")
        return None
    
    try:
        # Use provided browser or create a new one
        if browser:
            page = await browser.new_page()
            should_close_browser = False
        else:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                should_close_browser = True
        
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        await page.goto(url, wait_until="load")
        
        show_button_selectors = [
            # Primary selector with exact classes
            'button.Button_button__gLzwe.Button_type__secondary__q5NvJ.Button_outline__5lXwE',
            # Text-based selectors (most reliable for different languages)
            'button:has-text("Arată numărul")',
            'button:has-text("Показать номер")',
            # Class-based selectors (fallbacks)
            'button.Button_button__gLzwe.Button_type__secondary__q5NvJ',
            'button.Button_button__gLzwe.Button_outline__5lXwE',
            'button.Button_button__gLzwe',
            '.Button_button__gLzwe.Button_type__secondary__q5NvJ.Button_outline__5lXwE',
            '.Button_button__gLzwe.Button_type__secondary__q5NvJ',
            '.Button_button__gLzwe.Button_outline__5lXwE',
            '.Button_button__gLzwe',
            # Attribute-based selectors
            'button[class*="Button_button"][class*="Button_type__secondary"][class*="Button_outline"]',
            'button[class*="Button_button"][class*="Button_type__secondary"]',
            'button[class*="Button_button"][class*="Button_outline"]',
            'button[class*="Button_button"]',
            # Generic text fallback
            'button:has-text("Show number")'
        ]
        
        button_clicked = False
        for selector in show_button_selectors:
            try:
                button = page.locator(selector).first
                button_count = await button.count()
                if button_count > 0:
                    log_verbose(f"Found show number button with selector: {selector}")
                    await button.wait_for(state="visible", timeout=3000)
                    await button.click()
                    button_clicked = True
                    log_verbose("Successfully clicked show number button")
                    
                    # Wait for phone number to appear (wait for hidden class to be removed)
                    try:
                        # Wait for the hidden phone number to be revealed
                        # The structure shows: div.styles_number__koOQS > span.styles_number__hidden__exH2_
                        # After click, the hidden span should be replaced with the full number
                        await page.wait_for_function(
                            r"""() => {
                                const phoneDiv = document.querySelector('div.styles_number__koOQS');
                                if (!phoneDiv) return false;
                                
                                // Check if the hidden span is gone or if we have a full phone number
                                const hiddenSpan = phoneDiv.querySelector('span.styles_number__hidden__exH2_');
                                const phoneText = phoneDiv.innerText;
                                
                                // Phone number is revealed if:
                                // 1. Hidden span is gone, OR
                                // 2. We have a complete phone number pattern
                                const phoneRegex = /\+373\s*\d{2}\s*\d{3}\s*\d{3}/;
                                return !hiddenSpan || phoneRegex.test(phoneText);
                            }""",
                            timeout=5000
                        )
                        log_verbose("Phone number revealed in styles_number__koOQS div")
                    except:
                        # Fallback: wait for any complete phone number pattern
                        try:
                            await page.wait_for_function(
                                r"""() => {
                                    const phoneRegex = /\+373\s*\d{2}\s*\d{3}\s*\d{3}/;
                                    return phoneRegex.test(document.body.innerText);
                                }""",
                                timeout=3000
                            )
                            log_verbose("Complete phone number appeared in page content")
                        except:
                            # Final fallback: just wait a bit
                            await page.wait_for_timeout(2000)
                            log_verbose("Timeout waiting for phone number, proceeding anyway")
                    
                    break
            except Exception as e:
                log_verbose(f"Selector '{selector}' failed: {e}")
                continue
        
        if not button_clicked:
            log_verbose("Show number button not found with any selector, proceeding with current content")
            # Try to find any button that might contain phone-related text
            try:
                all_buttons = await page.locator('button').all()
                log_verbose(f"Found {len(all_buttons)} buttons on page")
                for i, btn in enumerate(all_buttons[:10]):  # Check first 10 buttons
                    try:
                        text = await btn.text_content()
                        classes = await btn.get_attribute('class')
                        log_verbose(f"Button {i}: text='{text}', classes='{classes}'")
                    except:
                        pass
            except Exception as e:
                log_verbose(f"Error inspecting buttons: {e}")
            
        html_content = await page.content()
        
        # Close page (always) and browser (only if we created it)
        await page.close()
        if should_close_browser:
            await browser.close()
        
        return html_content
            
    except Exception as e:
        log_verbose(f"Playwright error: {e}")
        return None

async def fetch_listing_data(url, browser=None):
    log_info(f"Processing: {url}")
    html_content = await get_html_with_revealed_phone(url, browser)
    
    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        log_verbose("Using Playwright HTML with revealed phone number")
    else:
        log_verbose("Falling back to HTTP GET method")
        connector = aiohttp.TCPConnector(limit_per_host=4)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                response = await aiohttp_request_with_retries(
                    session, url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15
                )
                if response is None:
                    raise aiohttp.ClientError("Failed after retries")
                text = await response.text()
                soup = BeautifulSoup(text, "html.parser")
            except Exception as e:
                print(f"Error fetching URL: {e}")
                sys.exit(1)
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else url

    # Price extraction
    price = {}
    price_container = soup.find("div", class_="styles_price__KKd_l")
    if price_container:
        main_tag = price_container.find("span", class_="styles_footer__main__8seZ7")
        if main_tag:
            text = main_tag.get_text(" ", strip=True).replace(u"\xa0", " ")
            m = re.search(r"([\d\s]+)\s*(\D+)$", text)
            if m:
                amt, sym = m.group(1).strip(), m.group(2).strip()
                key = {"€": "EUR", "$": "USD", "MDL": "MDL"}.get(sym, sym)
                price[key] = f"{amt} {sym}"
            else:
                price["MAIN"] = text

    # Description - clean HTML while preserving useful styling
    desc_tag = soup.find("div", class_="styles_description__8_RRa")
    if desc_tag:
        # Keep inner HTML, normalize different <br> variants to <br>
        raw_html = ''.join(str(x) for x in desc_tag.contents)
        raw_html = raw_html.replace('\r\n', '\n').strip()
        raw_html = re.sub(r'<br\s*/?>', '<br>', raw_html, flags=re.IGNORECASE)
        # If no explicit <br> present, convert plain newlines to <br>, preserving empty rows
        if '<br' not in raw_html.lower():
            token = '___NL2___'
            raw_html = re.sub(r'\n{2,}', token, raw_html)
            raw_html = raw_html.replace('\n', '<br>')
            raw_html = raw_html.replace(token, '<br><br>')
        # Clean the HTML and convert to plain text
        description = clean_description_html(raw_html)
    else:
        description = "N/A"

    # Enhanced Features extraction - separate characteristics from amenities
    features = {}  # Only for Caracteristici section
    amenities = {}  # For all other sections

    for grp in soup.find_all("div", class_="styles_group__aota8"):
        hdr = grp.find("h2")
        section_name = hdr.get_text(strip=True) if hdr else "Features"
        items = grp.find_all("li", class_="styles_group__feature__5ZWJy")
        data_map, simple = {}, []
        
        for li in items:
            k_elem = li.find("span", class_="styles_group__key__uRhnQ")
            v_elem = li.find(class_="styles_group__value__XN7OI")
            if k_elem and v_elem:
                data_map[k_elem.get_text(strip=True)] = v_elem.get_text(strip=True)
            elif k_elem:
                simple.append(k_elem.get_text(strip=True))
        
        section_data = data_map if data_map else simple
        
        # Separate: Caracteristici goes to features, everything else goes to amenities
        if section_name in ["Характеристики", "Caracteristici"]:
            # This is the main characteristics section - add it to features
            features[section_name] = section_data
        else:
            # All other sections (Adăugător, etc.) are amenities
            if isinstance(section_data, dict):
                amenities.update(section_data)
            elif isinstance(section_data, list):
                for item in section_data:
                    amenities[item] = True
                    
    # Create standardized features mapping and bilingual features
    source_lang = 'ro' if '/ro/' in url else 'ru'
    # Get the characteristics data for standard features mapping
    characteristics = features.get('Caracteristici') or features.get('Характеристики') or {}
    standard_features = map_scraped_features_to_standard(characteristics, source_lang)
    # Create bilingual features from the features dict (only Caracteristici section)
    bilingual_features = create_bilingual_features(features, source_lang)
    log_verbose(f"Mapped {sum(standard_features.values())} standard features from characteristics")
    log_verbose(f"Created bilingual features: {len(features)} sections, RO={len(bilingual_features['ro'])}, RU={len(bilingual_features['ru'])}")
    log_verbose(f"Extracted {len(amenities)} amenities")

    # Images
    images, seen = [], set()
    for btn in soup.select('div.slick-slide button[data-src]'):
        src = btn.get("data-src")
        if src and src not in seen:
            seen.add(src)
            images.append(src)

    # Address extraction - Enhanced for better geocoding
    address = "N/A"
    full_address_parts = []
    data_extra = {}
    
    region_container = soup.find("div", class_="styles_region__7lsaj")
    if region_container:
        # Remove the "Regiunea:" title and get the actual address
        region_title = region_container.find("span", class_="styles_region__title__PyqgH")
        if region_title:
            # Extract text after removing the title span
            full_text = region_container.get_text(strip=True)
            title_text = region_title.get_text(strip=True)
            raw_address = full_text.replace(title_text, "").strip()
        else:
            # Fallback: get all text from the container
            raw_address = region_container.get_text(strip=True)
        
        # Parse the address structure: "Chișinău mun., Chișinău, Buiucani, str. Buiucani, 2/B"
        # This follows 999.md format: Municipality, City, District, Street, Building
        if raw_address and raw_address != "N/A":
            parts = [part.strip() for part in raw_address.split(',')]
            log_verbose(f"🔍 Address parsing - Raw address: {raw_address}")
            log_verbose(f"🔍 Address parsing - Split parts: {parts}")
            
            # Extract meaningful parts for geocoding
            street_part = None
            building_number = None
            district = None
            city = "Chișinău"  # Default for Moldova
            
            for i, part in enumerate(parts):
                if ('str.' in part or 'bd.' in part or 'bdul.' in part or 
                    part.lower().startswith('strada ') or part.lower().startswith('bulevardul ') or 
                    part.lower().startswith('piața ') or part.lower().startswith('aleea ')):
                    # This is the street part
                    street_part = part.strip()
                    log_verbose(f"🔍 Found street part: {street_part}")
                    
                    # Check if the next part is a building number
                    if i + 1 < len(parts):
                        next_part = parts[i + 1].strip()
                        log_verbose(f"🔍 Checking next part for building number: '{next_part}'")
                        # Building number pattern: digits with optional letters/slashes (19/8, 23A, etc.)
                        if re.match(r'^[\d]+[\w/-]*$', next_part) and next_part not in ['Chișinău', 'Moldova']:
                            building_number = next_part
                            log_verbose(f"✅ Building number detected: {building_number}")
                        else:
                            log_verbose(f"❌ Not a building number: {next_part}")
                            
                elif 'mun.' not in part and part not in ['Chișinău', 'Moldova']:
                    # Skip if this is a building number we already captured
                    if building_number and part.strip() == building_number:
                        continue
                    
                    # Check if this part is a building number (could be at the end)
                    if not building_number and re.match(r'^[\d]+[\w/-]*$', part.strip()):
                        building_number = part.strip()
                        log_verbose(f"✅ Building number found at end: {building_number}")
                        continue
                        
                    # This might be a district or neighborhood
                    if not district:
                        district = part.strip()
                        log_verbose(f"🔍 Found district: {district}")
            
            # Build a structured address for better geocoding
            address_components = []
            if street_part:
                # Clean up street part but preserve building number
                street_clean = street_part.replace('str.', 'Strada').replace('bd.', 'Bulevardul').replace('bdul.', 'Bulevardul').strip()
                
                # Add building number to street if found
                if building_number:
                    street_with_building = f"{street_clean} {building_number}"
                    address_components.append(street_with_building)
                    log_verbose(f"📍 Preserved building number: {street_clean} → {street_with_building}")
                else:
                    address_components.append(street_clean)
            
            if district and district not in ['Chișinău', 'Moldova']:
                address_components.append(district)
            
            address_components.append(city)
            address_components.append('Moldova')
            
            # Create both a display address and a geocoding address
            address = raw_address  # Keep original for display
            geocoding_address = ', '.join(address_components) if address_components else raw_address
            
            log_verbose(f"🏠 Final address components: {address_components}")
            log_verbose(f"🏠 Display address: {address}")
            log_verbose(f"🏠 Geocoding address: {geocoding_address}")
            log_verbose(f"🏠 Building number: {building_number}")
            
            # Store both versions
            data_extra = {
                'display_address': address,
                'geocoding_address': geocoding_address,
                'street_part': street_part,
                'building_number': building_number,
                'district': district
            }
        else:
            address = raw_address
            data_extra = {'display_address': address, 'geocoding_address': address}
    

    # Contact extraction - look for the revealed phone number
    contact = "N/A"
    
    # Based on the structure: div.styles_number__koOQS contains the phone number
    # After button click, it should contain the full number instead of the hidden span
    phone_divs = soup.find_all("div", class_="styles_number__koOQS")
    for phone_div in phone_divs:
        phone_text = phone_div.get_text(strip=True)
        # Clean up the phone text (remove extra spaces and formatting)
        phone_clean = ' '.join(phone_text.split())
        
        # Check if this looks like a complete phone number (should have +373 and proper length)
        if phone_clean and "+373" in phone_clean and len(phone_clean.replace(" ", "")) >= 12:
            # Make sure it's not the hidden version (which has dots/dashes)
            if not ("..." in phone_clean or "••" in phone_clean or "i" in phone_clean):
                contact = phone_clean
                log_verbose(f"Found revealed phone number in div: {contact}")
                break
    
    # Fallback: Search within footer if not found above
    if contact == "N/A":
        footer = soup.find("footer", class_="styles_footer__sKQxZ")
        if footer:
            # Look for phone number in footer
            phone_elements = footer.find_all(class_="styles_number__koOQS")
            for phone_element in phone_elements:
                phone_text = phone_element.get_text(strip=True)
                phone_clean = ' '.join(phone_text.split())
                if phone_clean and "+373" in phone_clean and len(phone_clean.replace(" ", "")) >= 12:
                    if not ("..." in phone_clean or "••" in phone_clean or "i" in phone_clean):
                        contact = phone_clean
                        log_verbose(f"Found phone in footer element: {contact}")
                        break
    
    # Additional fallback methods
    if contact == "N/A":
        # Method: Look for any element with phone class that might contain revealed number
        phone_elements = soup.find_all(class_="styles_number__koOQS")
        for phone_element in phone_elements:
            # Check if it has a span inside
            phone_span = phone_element.find("span")
            if phone_span and not phone_span.get("class") == ["styles_number__hidden__exH2_"]:
                phone_text = phone_span.get_text(strip=True)
                phone_clean = ' '.join(phone_text.split())
                if phone_clean and "+373" in phone_clean:
                    contact = phone_clean
                    log_verbose(f"Found phone in non-hidden span: {contact}")
                    break
            else:
                # Get text from the element itself
                phone_text = phone_element.get_text(strip=True)
                phone_clean = ' '.join(phone_text.split())
                if phone_clean and "+373" in phone_clean and len(phone_clean.replace(" ", "")) >= 12:
                    if not ("..." in phone_clean or "••" in phone_clean or "i" in phone_clean):
                        contact = phone_clean
                        log_verbose(f"Found phone in element text: {contact}")
                        break
        
        # Method 3: Look for tel: links as final fallback
        if contact == "N/A":
            # Check for tel: links anywhere in the page
            tel_links = soup.find_all("a", href=lambda x: x and x.startswith("tel:"))
            if tel_links:
                # Extract phone from href attribute
                tel_href = tel_links[0].get("href")
                if tel_href:
                    contact = tel_href.replace("tel:", "").strip()
                    log_verbose(f"Found phone in tel: link: {contact}")
        
        # Method 4: Look for phone in data attributes or aria-labels
        if contact == "N/A":
            # Check all elements in the page for phone-like data
            all_elements = soup.find_all(attrs={"data-phone": True})
            if not all_elements:
                all_elements = soup.find_all(attrs={"aria-label": lambda x: x and "+" in str(x)})
            
            for element in all_elements:
                data_phone = element.get("data-phone") or element.get("aria-label")
                if data_phone and "+" in data_phone:
                    contact = data_phone
                    log_verbose(f"Found phone in data attribute: {contact}")
                    break
    
    # Contact extraction completed
    

    map_data = None
    
    # Try to get map data from the page (Yandex Maps) as a fallback available during parsing
    if not map_data:
        map_script = soup.find("script", string=re.compile(r"ymaps.ready"))
        if map_script:
            match = re.search(r'center: \[(\d+\.\d+), (\d+\.\d+)\]',
                              map_script.string)
            if match:
                map_data = {
                    "lat": float(match.group(1)),
                    "lng": float(match.group(2)),
                    "title": title
                }

    # Add the extra address data to the return dict if it exists
    result = {
        "url": url,
        "title": title,
        "price": price,
        "description": description,
        "features": features,  # ✅ FIXED: Store ALL feature sections, not just characteristics
        "amenities": amenities,       # Store amenities separately
        "standard_features": standard_features,
        "bilingual_features": bilingual_features,
        "images": images,
        "address": address,
        "contact": contact,
        "map_data": map_data
    }
    
    # Add enhanced address data if available
    if 'data_extra' in locals():
        result.update(data_extra)
    
    return result

# --- Retry/backoff helpers and caching ---
import time
import hashlib
from datetime import datetime, timezone
from contextlib import asynccontextmanager

async def aiohttp_request_with_retries(session, url, method='GET', retries=3, backoff=0.5, **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            resp = await session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = e
            sleep_time = backoff * (2 ** attempt)
            await asyncio.sleep(sleep_time)
    log_verbose(f"HTTP request failed after {retries} retries: {url} - {last_err}")
    return None

# Geocoding cache stored inside the per-listing listings.db

def _ensure_geocode_cache_schema_in(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS geocode_cache (
        key TEXT PRIMARY KEY,
        lat REAL,
        lng REAL,
        title TEXT,
        created_at TEXT
    )''')
    conn.commit()

def _normalize_address_key(display_address, geocoding_address):
    base = (geocoding_address or display_address or '').strip().lower()
    base = re.sub(r'\s+', ' ', base)
    return hashlib.sha1(base.encode('utf-8')).hexdigest() if base else None

async def geocode_with_cache(display_address, geocoding_address, db_path):
    key = _normalize_address_key(display_address, geocoding_address)
    if not key:
        return None
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('PRAGMA journal_mode=WAL')  # Use WAL for better concurrent access
        _ensure_geocode_cache_schema_in(conn)
        c = conn.cursor()
        c.execute('SELECT lat, lng, title FROM geocode_cache WHERE key = ?', (key,))
        row = c.fetchone()
        if row:
            return {"lat": row[0], "lng": row[1], "title": display_address}
    finally:
        conn.close()

    # Not cached: perform geocoding
    result = await geocode_address(display_address, geocoding_address)
    if result:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute('PRAGMA journal_mode=WAL')  # Use WAL for better concurrent access
            _ensure_geocode_cache_schema_in(conn)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO geocode_cache (key, lat, lng, title, created_at) VALUES (?,?,?,?,?)',
                      (key, result['lat'], result['lng'], result.get('title', display_address), datetime.now(timezone.utc).isoformat()))
            conn.commit()
        finally:
            conn.close()
    return result

# --- Advanced geocoding fallback methods ---
async def nominatim_structured_async(session, street_name, building, district, city='Chișinău', country='Moldova'):
    """Use Nominatim structured parameters for better address matching."""
    params = {
        'format': 'json',
        'limit': '5',
        'countrycodes': 'md',
        'addressdetails': '1',
        'street': f"{street_name} {building}" if building else street_name,
        'city': city,
        # Nominatim uses 'county' for some admin levels; try district as county to bias search
        'county': district or ''
    }
    query = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params)
    try:
        resp = await aiohttp_request_with_retries(session, query, headers={'User-Agent': 'RealAgent/1.0'}, timeout=10)
        if not resp:
            return None
        data = await resp.json()
        if not data:
            return None
        # Prefer house/building results
        best = None
        for item in data:
            item_type = item.get('type', '')
            cls = item.get('class', '')
            score = 0
            if item_type in ['house', 'building'] or cls == 'building':
                score += 60
            if street_name.lower() in item.get('display_name', '').lower():
                score += 20
            if building and building.lower() in item.get('display_name', '').lower():
                score += 20
            item['_score'] = score
            if not best or score > best['_score']:
                best = item
        if best:
            return {
                'lat': float(best.get('lat', 0)),
                'lng': float(best.get('lon', 0)),
                'title': f"{street_name} {building}, {district or city}",
            }
        return None
    except Exception as e:
        log_verbose(f"Structured Nominatim fallback failed: {e}")
        return None

async def overpass_street_centroid_async(session, street_name, city='Chișinău'):
    """Query Overpass API for a street by name and return its centroid within the city."""
    overpass_url = 'https://overpass-api.de/api/interpreter'
    # Query: find area by name city, then ways with highway and given name; output center of first match
    q = f"[out:json][timeout:12];area[name=\"{city}\"]->.a;way(area.a)[\"highway\"][\"name\"=\"{street_name}\"];out center 1;"
    try:
        resp = await aiohttp_request_with_retries(
            session,
            overpass_url + '?data=' + urllib.parse.quote(q),
            timeout=15
        )
        if not resp:
            return None
        data = await resp.json()
        elements = data.get('elements') or []
        for el in elements:
            center = el.get('center')
            if center and 'lat' in center and 'lon' in center:
                return {
                    'lat': center['lat'],
                    'lng': center['lon'],
                    'title': f"{street_name}, {city}"
                }
        return None
    except Exception as e:
        log_verbose(f"Overpass fallback failed: {e}")
        return None

async def enhanced_fallback_attempts(session, parsed, geocoding_address, display_title):
    """Enhanced fallback with 3 different methods when score < 50.
    
    Method 1: Fuzzy address matching with relaxed constraints
    Method 2: Component-based geocoding (street, district, city separately)
    Method 3: Alternative geocoding services and manual coordinate lookup
    """
    log_verbose("=== ENHANCED FALLBACK: 3-Method Approach ===")
    
    # Method 1: Fuzzy address matching with relaxed constraints
    log_verbose("Method 1: Fuzzy address matching...")
    fuzzy_result = await fuzzy_address_matching(session, parsed, display_title)
    if fuzzy_result:
        return fuzzy_result
    
    # Method 2: Component-based geocoding
    log_verbose("Method 2: Component-based geocoding...")
    component_result = await component_based_geocoding(session, parsed, display_title)
    if component_result:
        return component_result
    
    # Method 3: Alternative services and manual lookup
    log_verbose("Method 3: Alternative services and manual lookup...")
    alternative_result = await alternative_geocoding_services(session, parsed, geocoding_address, display_title)
    if alternative_result:
        return alternative_result
    
    log_verbose("All 3 enhanced fallback methods failed.")
    return None

async def fuzzy_address_matching(session, parsed, display_title):
    """Method 1: Try fuzzy matching with various address permutations."""
    street_name = parsed.get('street_name', '')
    building = parsed.get('building', '')
    district = parsed.get('district', '')
    
    # Create multiple fuzzy query variations
    fuzzy_queries = []
    
    if street_name:
        # Try without building number
        fuzzy_queries.append(f"{street_name}, Chișinău, Moldova")
        # Try with 'strada' prefix variations
        fuzzy_queries.append(f"strada {street_name}, Chișinău")
        fuzzy_queries.append(f"str {street_name}, Chișinău")
        # Try with district if available
        if district:
            fuzzy_queries.append(f"{street_name}, {district}, Chișinău")
            fuzzy_queries.append(f"strada {street_name}, {district}")
    
    if district:
        # Try district-only queries
        fuzzy_queries.append(f"{district}, Chișinău, Moldova")
        fuzzy_queries.append(f"sectorul {district}, Chișinău")
    
    # Test each fuzzy query
    for query in fuzzy_queries:
        log_verbose(f"  Fuzzy attempt: {query}")
        try:
            results = await query_geocoding_services_async(session, query)
            if results:
                best_result, score = score_and_select_best(results, parsed)
                if best_result and score >= 30:  # Lower threshold for fuzzy matching
                    log_verbose(f"  Fuzzy match success! Score: {score}")
                    return {
                        'lat': best_result['lat'],
                        'lng': best_result['lon'],
                        'title': display_title or query,
                        'method': 'fuzzy_matching'
                    }
        except Exception as e:
            log_verbose(f"  Fuzzy query failed: {e}")
    
    return None

async def component_based_geocoding(session, parsed, display_title):
    """Method 2: Geocode each component separately and combine."""
    street_name = parsed.get('street_name', '')
    district = parsed.get('district', '')
    
    # Extract city dynamically from original address
    original_addr = parsed.get('original_address', '').lower()
    city = 'Chișinău'  # Default fallback
    
    moldovan_cities = ['chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat']
    for city_name in moldovan_cities:
        if city_name in original_addr:
            city = city_name.title()
            break
    
    best_lat, best_lng = None, None
    confidence_score = 0
    
    # Try to get district coordinates
    if district:
        try:
            district_query = f"{district}, {city}, Moldova"
            resp = await aiohttp_request_with_retries(
                session,
                f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(district_query)}&format=json&limit=3&countrycodes=md",
                headers={'User-Agent': 'RealAgent/1.0'},
                timeout=10
            )
            if resp:
                data = await resp.json()
                for item in data:
                    if any(word in item.get('type', '').lower() for word in ['suburb', 'neighbourhood', 'district', 'quarter']):
                        best_lat, best_lng = float(item['lat']), float(item['lon'])
                        confidence_score += 40
                        print(f"  District coordinates found: {best_lat}, {best_lng}")
                        break
        except Exception as e:
            print(f"  District component failed: {e}")
    
    # If no district coordinates, try street-level
    if not best_lat and street_name:
        try:
            street_query = f"strada {street_name}, {city}, Moldova"
            resp = await aiohttp_request_with_retries(
                session,
                f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(street_query)}&format=json&limit=3&countrycodes=md",
                headers={'User-Agent': 'RealAgent/1.0'},
                timeout=10
            )
            if resp:
                data = await resp.json()
                if data:
                    best_lat, best_lng = float(data[0]['lat']), float(data[0]['lon'])
                    confidence_score += 30
        except Exception as e:
            print(f"  Street component failed: {e}")
    
    # Fallback to city center if nothing else worked
    if not best_lat:
        log_verbose("  Component: Using city center as fallback")
        best_lat, best_lng = 47.0105, 28.8638  # Chișinău city center
        confidence_score += 20
    
    if confidence_score >= 20:
        log_verbose(f"  Component-based success! Confidence: {confidence_score}")
        return {
            'lat': best_lat,
            'lng': best_lng,
            'title': display_title or f"{street_name or district or 'Chișinău'}",
            'method': 'component_based',
            'confidence': confidence_score
        }
    
    return None

async def alternative_geocoding_services(session, parsed, geocoding_address, display_title):
    """Method 3: Try alternative geocoding services and manual coordinate lookup."""
    street_name = parsed.get('street_name', '')
    district = parsed.get('district', '')
    
    # Try MapBox Geocoding API (if available)
    log_verbose("  Alternative: Trying additional geocoding approaches...")
    
    # Manual coordinate lookup for known Chișinău districts/areas
    known_areas = {
        'centru': (47.0245, 28.8322),
        'botanica': (47.0186, 28.8267),
        'ciocana': (47.0641, 28.8981),
        'râșcani': (47.0411, 28.8186),
        'buiucani': (46.9975, 28.8089),
        'telecentru': (47.0105, 28.8638),
        'sculeni': (47.1089, 28.7969),
        'durlești': (47.0186, 28.7267)
    }
    
    # Check if district matches known areas
    if district:
        district_lower = district.lower()
        for area, coords in known_areas.items():
            if area in district_lower or district_lower in area:
                print(f"  Manual lookup: Found coordinates for {district}")
                return {
                    'lat': coords[0],
                    'lng': coords[1],
                    'title': display_title or f"{district}, Chișinău",
                    'method': 'manual_lookup',
                    'area': area
                }
    
    # Try OpenCage Geocoding API format (alternative query structure)
    if street_name or district:
        alternative_query = f"{street_name or ''} {district or ''} Chișinău Moldova".strip()
        print(f"  Alternative query format: {alternative_query}")
        try:
            # Use Photon with different parameters
            photon_url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(alternative_query)}&limit=5&osm_tag=place&osm_tag=highway"
            resp = await aiohttp_request_with_retries(session, photon_url, timeout=10)
            if resp:
                data = await resp.json()
                features = data.get('features', [])
                if features:
                    feature = features[0]
                    coords = feature['geometry']['coordinates']
                    print(f"  Alternative service success!")
                    return {
                        'lat': coords[1],
                        'lng': coords[0],
                        'title': display_title or alternative_query,
                        'method': 'alternative_service'
                    }
        except Exception as e:
            log_verbose(f"  Alternative service failed: {e}")
    
    # Final fallback: Use detected city center with slight random offset to avoid clustering
    import random
    
    # Extract city dynamically (same logic as other functions)
    original_addr = parsed.get('original_address', '').lower()
    fallback_city = 'Chișinău'  # Default
    fallback_coords = (47.0105, 28.8638)  # Chișinău coordinates
    
    # City coordinate mappings for major Moldovan cities
    city_coords = {
        'chișinău': (47.0105, 28.8638),
        'chisinau': (47.0105, 28.8638),
        'bălți': (47.7615, 27.9297),
        'balti': (47.7615, 27.9297),
        'tiraspol': (46.8403, 29.6433),
        'bender': (46.8317, 29.4767),
        'tighina': (46.8317, 29.4767),
        'cahul': (45.9075, 28.1944),
        'ungheni': (47.2111, 27.8028),
        'soroca': (48.1581, 28.2939),
        'orhei': (47.3833, 28.8167),
        'comrat': (46.3058, 28.6653)
    }
    
    # Detect city from address
    moldovan_cities = ['chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat']
    for city_name in moldovan_cities:
        if city_name in original_addr:
            fallback_city = city_name.title()
            fallback_coords = city_coords.get(city_name, (47.0105, 28.8638))
            break
    
    offset_lat = random.uniform(-0.01, 0.01)
    offset_lng = random.uniform(-0.01, 0.01)
    
    log_verbose(f"  Using {fallback_city} city center with random offset as final fallback")
    return {
        'lat': fallback_coords[0] + offset_lat,
        'lng': fallback_coords[1] + offset_lng,
        'title': display_title or f"{fallback_city}, Moldova",
        'method': 'city_center_offset'
    }

async def advanced_geocoding_fallback(session, parsed, geocoding_address, display_title):
    """Try prioritized geocoding: City > Street > District for optimal balance."""
    street_name = parsed.get('street_name')
    building = parsed.get('building')
    district = parsed.get('district')
    
    # Extract city dynamically from original address (same logic as score_result)
    original_addr = parsed.get('original_address', '').lower()
    city = 'Chișinău'  # Default fallback
    
    # Common Moldovan cities to detect from address
    moldovan_cities = ['chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat']
    for city_name in moldovan_cities:
        if city_name in original_addr:
            city = city_name.title()  # Capitalize for queries
            break
    
    log_verbose(f"Advanced fallback: Using city '{city}' from address analysis")

    # Priority 1: City-level coordinates (most reliable baseline)
    log_verbose("Advanced fallback: Trying city-level coordinates...")
    city_q = f"{city}, Moldova"
    city_result = None
    try:
        resp = await aiohttp_request_with_retries(
            session,
            f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(city_q)}&format=json&limit=1&countrycodes=md",
            headers={'User-Agent': 'RealAgent/1.0'},
            timeout=10
        )
        if resp:
            data = await resp.json()
            if data and data[0].get('type') in ['city', 'town', 'municipality']:
                city_result = {
                    'lat': float(data[0].get('lat', 0)),
                    'lng': float(data[0].get('lon', 0)),
                    'title': display_title or city_q,
                    'priority_level': 'city'
                }
                log_verbose("Advanced fallback: City-level coordinates found")
    except Exception as e:
        log_verbose(f"City-level fallback failed: {e}")

    # Priority 2: Street-level coordinates within the city (even without house number)
    if street_name:
        log_verbose("Advanced fallback: Trying to pinpoint street within city...")
        
        # 2a) Structured Nominatim with street/building/city/district
        structured = await nominatim_structured_async(session, street_name, building, district, city=city)
        if structured:
            structured['title'] = display_title or structured.get('title')
            structured['priority_level'] = 'street'
            log_verbose("Advanced fallback: structured Nominatim succeeded")
            return structured

        # 2b) Overpass street centroid (approximate street location)
        centroid = await overpass_street_centroid_async(session, street_name, city=city)
        if centroid:
            centroid['title'] = display_title or centroid.get('title')
            centroid['priority_level'] = 'street'
            log_verbose("Advanced fallback: Overpass street centroid used")
            return centroid

        # 2c) Street name search within city (even without house number)
        street_q = f"{street_name}, {city}, Moldova"
        try:
            resp = await aiohttp_request_with_retries(
                session,
                f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(street_q)}&format=json&limit=5&countrycodes=md",
                headers={'User-Agent': 'RealAgent/1.0'},
                timeout=10
            )
            if resp:
                data = await resp.json()
                # Look for highway/street results first (best match for street location)
                for item in data:
                    if item.get('class') == 'highway' or 'street' in item.get('type', '').lower():
                        log_verbose("Advanced fallback: Using street search result (highway/street)")
                        return {
                            'lat': float(item.get('lat', 0)),
                            'lng': float(item.get('lon', 0)),
                            'title': display_title or street_q,
                            'priority_level': 'street'
                        }
                
                # Look for any result that contains the street name within the city
                for item in data:
                    display_name = item.get('display_name', '').lower()
                    if (street_name.lower() in display_name and 
                        city.lower() in display_name):
                        log_verbose("Advanced fallback: Using street name match within city")
                        return {
                            'lat': float(item.get('lat', 0)),
                            'lng': float(item.get('lon', 0)),
                            'title': display_title or street_q,
                            'priority_level': 'street'
                        }
        except Exception as e:
            log_verbose(f"Street search fallback failed: {e}")

        # 2d) Try street without building number if we had one
        if building:
            street_only_q = f"{street_name}, {city}, Moldova"
            try:
                resp = await aiohttp_request_with_retries(
                    session,
                    f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(street_only_q)}&format=json&limit=3&countrycodes=md",
                    headers={'User-Agent': 'RealAgent/1.0'},
                    timeout=10
                )
                if resp:
                    data = await resp.json()
                    if data:
                        log_verbose("Advanced fallback: Using street without building number")
                        return {
                            'lat': float(data[0].get('lat', 0)),
                            'lng': float(data[0].get('lon', 0)),
                            'title': display_title or street_only_q,
                            'priority_level': 'street'
                        }
            except Exception as e:
                log_verbose(f"Street-only search failed: {e}")

    # Priority 3: District-level coordinates (if district exists)
    if district:
        log_verbose("Advanced fallback: Trying district-level coordinates...")
        district_q = f"{district}, {city}, Moldova"
        try:
            resp = await aiohttp_request_with_retries(
                session,
                f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(district_q)}&format=json&limit=1&countrycodes=md",
                headers={'User-Agent': 'RealAgent/1.0'},
                timeout=10
            )
            if resp:
                data = await resp.json()
                if data:
                    log_verbose("Advanced fallback: Using district-level coordinates")
                    return {
                        'lat': float(data[0].get('lat', 0)),
                        'lng': float(data[0].get('lon', 0)),
                        'title': display_title or district_q,
                        'priority_level': 'district'
                    }
        except Exception as e:
            log_verbose(f"District centroid fallback failed: {e}")

    # Final fallback: Return city coordinates if we found them
    if city_result:
        log_verbose("Advanced fallback: Using city-level coordinates as final fallback")
        return city_result

    return None


# --- Lightweight text-only extraction for alternate language (no phone scraping) ---
async def fetch_listing_text_only(url):
    # Use simple HTTP request without phone number revelation to avoid double scraping
    connector = aiohttp.TCPConnector(limit_per_host=4)
    async with aiohttp.ClientSession(connector=connector) as session:
        response = await aiohttp_request_with_retries(
            session, url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15
        )
        if response is None:
            raise aiohttp.ClientError("Failed after retries")
        text = await response.text()
        soup = BeautifulSoup(text, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else url

    # Description - clean HTML while preserving useful styling
    desc_tag = soup.find("div", class_="styles_description__8_RRa")
    if desc_tag:
        raw_html = ''.join(str(x) for x in desc_tag.contents)
        raw_html = raw_html.replace('\r\n', '\n').strip()
        raw_html = re.sub(r'<br\s*/?>', '<br>', raw_html, flags=re.IGNORECASE)
        if '<br' not in raw_html.lower():
            token = '___NL2___'
            raw_html = re.sub(r'\n{2,}', token, raw_html)
            raw_html = raw_html.replace('\n', '<br>')
            raw_html = raw_html.replace(token, '<br><br>')
        # Clean the HTML and convert to plain text
        description = clean_description_html(raw_html)
    else:
        description = "N/A"

    # Price extraction (text-only variant builds same dict shape)
    price = {}
    price_container = soup.find("div", class_="styles_price__KKd_l")
    if price_container:
        main_tag = price_container.find("span", class_="styles_footer__main__8seZ7")
        if main_tag:
            text = main_tag.get_text(" ", strip=True).replace(u"\xa0", " ")
            m = re.search(r"([\d\s]+)\s*(\D+)$", text)
            if m:
                amt, sym = m.group(1).strip(), m.group(2).strip()
                key = {"€": "EUR", "$": "USD", "MDL": "MDL"}.get(sym, sym)
                price[key] = f"{amt} {sym}"
            else:
                price["MAIN"] = text

    # Enhanced Features extraction - separate characteristics from amenities
    features = {}  # Only for Caracteristici section
    amenities = {}  # For all other sections

    for grp in soup.find_all("div", class_="styles_group__aota8"):
        hdr = grp.find("h2")
        section_name = hdr.get_text(strip=True) if hdr else "Features"
        items = grp.find_all("li", class_="styles_group__feature__5ZWJy")
        data_map, simple = {}, []
        
        for li in items:
            k_elem = li.find("span", class_="styles_group__key__uRhnQ")
            v_elem = li.find(class_="styles_group__value__XN7OI")
            if k_elem and v_elem:
                data_map[k_elem.get_text(strip=True)] = v_elem.get_text(strip=True)
            elif k_elem:
                simple.append(k_elem.get_text(strip=True))
        
        section_data = data_map if data_map else simple
        
        # Separate: Caracteristici goes to features, everything else goes to amenities
        if section_name in ["Характеристики", "Caracteristici"]:
            # This is the main characteristics section - add it to features
            features[section_name] = section_data
        else:
            # All other sections (Adăugător, etc.) are amenities
            if isinstance(section_data, dict):
                amenities.update(section_data)
            elif isinstance(section_data, list):
                for item in section_data:
                    amenities[item] = True    
                    
    # Create standardized features mapping and bilingual features
    source_lang = 'ro' if '/ro/' in url else 'ru'
    # Get the characteristics data for standard features mapping
    characteristics = features.get('Caracteristici') or features.get('Характеристики') or {}
    standard_features = map_scraped_features_to_standard(characteristics, source_lang)
    # Create bilingual features from the features dict (only Caracteristici section)
    bilingual_features = create_bilingual_features(features, source_lang)
    log_verbose(f"Mapped {sum(standard_features.values())} standard features from characteristics")
    log_verbose(f"Created bilingual features: {len(features)} sections, RO={len(bilingual_features['ro'])}, RU={len(bilingual_features['ru'])}")
    log_verbose(f"Extracted {len(amenities)} amenities")

    # Address
    address = "N/A"
    region_container = soup.find("div", class_="styles_region__7lsaj")
    if region_container:
        region_title = region_container.find("span", class_="styles_region__title__PyqgH")
        if region_title:
            full_text = region_container.get_text(strip=True)
            title_text = region_title.get_text(strip=True)
            address = full_text.replace(title_text, "").strip()
        else:
            address = region_container.get_text(strip=True)

    # Note: Contact info is not extracted here to avoid double phone number scraping
    # The contact will be reused from the main scraping with phone revelation

    return {
        "title": title,
        "description": description,
        "features": features,  # ✅ FIXED: Store ALL feature sections, not just characteristics
        "amenities": amenities,       # Store amenities separately
        "standard_features": standard_features,
        "bilingual_features": bilingual_features,
        "address": address,
        "price": price,
        "contact": "N/A"  # Will be overridden with main contact info
    }

# --- Image processing removed - keeping original formats for hosting service ---

# Share image creation functions removed - using Open Graph with regular images instead

# --- Per-listing Processing (async image pipeline + expanded DB) ---
async def _download_one_image(session, semaphore, src, img_dir, folder, index):
    async with semaphore:
        try:
            resp = await aiohttp_request_with_retries(session, src, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if resp is None:
                raise RuntimeError("download failed after retries")
            content = await resp.read()
            
            # Convert to WebP format
            try:
                # Open image from bytes
                img = Image.open(BytesIO(content))
                
                # Convert RGBA to RGB if necessary (WebP doesn't support transparency in all modes)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Generate WebP filename
                fname = f"image_{index}.webp"
                full_path = os.path.join(img_dir, fname)
                
                # Save as WebP with quality 100.
                img.save(full_path, 'WEBP', quality=100, method=6)
                
                return os.path.relpath(full_path, folder).replace(os.sep, '/')
                
            except Exception as e:
                # Fallback: save original if WebP conversion fails
                log_warning(f"WebP conversion failed for image {index}, saving original: {e}")
                fname = os.path.basename(src.split('?')[0])
                if not fname or '.' not in fname:
                    fname = f"image_{index+1}.jpg"
                full_path = os.path.join(img_dir, fname)
                with open(full_path, 'wb') as f:
                    f.write(content)
                return os.path.relpath(full_path, folder).replace(os.sep, '/')
                
        except Exception as e:
            print(f"Error downloading image {src}: {e}")
            return None

async def download_images_async(urls, img_dir, folder, concurrency=6):
    os.makedirs(img_dir, exist_ok=True)
    connector = aiohttp.TCPConnector(limit_per_host=4)
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            _download_one_image(session, semaphore, src, img_dir, folder, i)
            for i, src in enumerate(urls)
        ]
        results = await asyncio.gather(*tasks)
    return [r for r in results if r]


async def process_listing(url, browser=None, template_name='luna'):
    data = await fetch_listing_data(url, browser)
    parsed = urllib.parse.urlparse(url)
    
    # Extract clean listing ID from URL
    # For 999.md URLs like: https://999.md/ro/100650877
    # Extract just the numeric ID: 100650877
    parts = [p for p in parsed.path.strip('/').split('/') if p]
    listing_id = None
    
    # Find the numeric listing ID in the URL parts
    for part in reversed(parts):  # Check from end to start
        if part.isdigit():
            listing_id = part
            break
    
    # Fallback to original method if no numeric ID found
    if not listing_id:
        domain = parsed.netloc.replace('.', '_')
        last = parts[-1] if parts else domain
        listing_id = f"{domain}_{last}"
    
    # Create clean folder structure: Listings/[ID]/
    folder = f"Listings/{listing_id}"
    os.makedirs(folder, exist_ok=True)
    
    log_verbose(f"Creating listing folder: {folder}")

    # Enhanced dual-language scraping for 999.md
    url_path = parsed.path or ''
    is_999md = '999.md' in parsed.netloc
    
    if is_999md:
        log_info(f"🌐 Detected 999.md URL - implementing dual-language scraping")
        
        # Determine current language and create both URLs
        provided_lang = 'ro' if '/ro/' in url_path else ('ru' if '/ru/' in url_path else 'ro')
        other_lang = 'ru' if provided_lang == 'ro' else 'ro'
        
        # Create both language URLs
        if '/ro/' in url:
            ro_url = url
            ru_url = url.replace('/ro/', '/ru/')
        elif '/ru/' in url:
            ru_url = url
            ro_url = url.replace('/ru/', '/ro/')
        else:
            # If no language specified, create both variants
            base_url = url.rstrip('/')
            ro_url = f"{base_url.replace(parsed.path, '')}/ro{parsed.path}"
            ru_url = f"{base_url.replace(parsed.path, '')}/ru{parsed.path}"
        
        log_info(f"📄 Romanian URL: {ro_url}")
        log_info(f"📄 Russian URL: {ru_url}")
        
        # Scrape both languages
        localized = {}
        
        # Primary language (already scraped)
        localized[provided_lang] = {
            'title': data.get('title'),
            'description': data.get('description'),
            'features': data.get('features'),
            'amenities': data.get('amenities'),
            'address': data.get('geocoding_address', data.get('address')),  # Use geocoding_address (with building number) for display
            'price': data.get('price'),
            'contact': data.get('contact')
        }
        
        # Scrape alternate language with full data extraction
        try:
            alt_url = ru_url if provided_lang == 'ro' else ro_url
            alt_data = await fetch_listing_data(alt_url)
            
            localized[other_lang] = {
                'title': alt_data.get('title'),
                'description': alt_data.get('description'),
                'features': alt_data.get('features'),
                'amenities': alt_data.get('amenities'),
                'address': alt_data.get('geocoding_address', alt_data.get('address')),  # Use geocoding_address (with building number) for display
                'price': alt_data.get('price'),
                'contact': data.get('contact')  # Use primary contact (with phone)
            }
            
        except Exception as e:
            log_warning(f"Failed to scrape alternate language from {alt_url}: {e}")
            # Fallback to text-only extraction
            try:
                alt_text = await fetch_listing_text_only(alt_url)
                if alt_text:
                    alt_text['contact'] = data.get('contact')
                    localized[other_lang] = alt_text
                    log_info(f"📝 Fallback: extracted text-only for {other_lang.upper()}")
            except Exception as e2:
                log_warning(f"Text-only fallback also failed: {e2}")
                localized[other_lang] = None
    else:
        # Non-999.md URLs - use existing logic
        provided_lang = 'ro'  # Default for other sites
        other_lang = 'ru'
        
        localized = {
            provided_lang: {
                'title': data.get('title'),
                'description': data.get('description'),
                'features': data.get('features'),
                'amenities': data.get('amenities'),
                'address': data.get('geocoding_address', data.get('address')),  # Use geocoding_address (with building number) for display
                'price': data.get('price'),
                'contact': data.get('contact')
            }
        }

    # Async image downloads with WebP conversion
    img_dir = os.path.join(folder, 'images')
    local_imgs = await download_images_async(data['images'], img_dir, folder)
    
    # Images automatically converted to WebP format for optimization
    print(f"✅  Downloaded and converted {len(local_imgs)} images to WebP.")
    print()  # Add space after download images line

    # Geocode with centralized cache in Mainframe.db
    if not data.get('map_data'):
        geocoding_result = await geocode_with_cache(
            data.get('address'),
            data.get('geocoding_address', data.get('address')),
            'Mainframe.db'  # Centralized geocoding cache
        )
        data['map_data'] = geocoding_result
        
        # If user provided a corrected address, update all address-related fields
        if geocoding_result and geocoding_result.get('corrected_address'):
            corrected_addr = geocoding_result['corrected_address']
            # log_info(f"Updating all address fields with user-corrected address: {corrected_addr}")
            print()  # Add blank line for better readability
            
            # Update main address field
            data['address'] = corrected_addr
            
            # Update geocoding address if it exists
            if 'geocoding_address' in data:
                data['geocoding_address'] = corrected_addr
            
            # Update the title field in map_data for Leaflet marker display
            if data.get('map_data'):
                data['map_data']['title'] = corrected_addr
            
            # Update any address-related fields in the data structure
            for key in data.keys():
                if 'address' in key.lower():
                    data[key] = corrected_addr
            
            # CRITICAL: Update the localized dictionary with corrected address
            # This ensures the corrected address appears in the final HTML
            for lang_key in localized.keys():
                if localized[lang_key]:
                    localized[lang_key]['address'] = corrected_addr
            
            # Mark this address as user-corrected to prevent re-formatting
            data['user_corrected_address'] = True
    
    # ============================================================================
    # Fetch POI data for this location (pre-generate to eliminate runtime API calls)
    # ============================================================================
    poi_data = {}
    poi_summary = {}
    
    if data.get('map_data') and data['map_data'].get('lat') and data['map_data'].get('lng'):
        try:
            from Helper.poi_fetcher import fetch_pois_for_listing
            
            lat = float(data['map_data']['lat'])
            lng = float(data['map_data']['lng'])
            
            # Fetch POI data with 500m radius
            poi_data, poi_summary = await fetch_pois_for_listing(lat, lng, radius=500)
            
            print(f"✅ Fetched {poi_summary.get('total_pois', 0)} POIs across {len(poi_summary.get('categories', {}))} categories")
            
        except Exception as e:
            print(f"⚠️ Warning: Failed to fetch POI data: {e}")
            # Continue without POI data - not critical for basic functionality
            poi_data = {}
            poi_summary = {}
    else:
        print("⚠️ No coordinates available - skipping POI data fetching")
    
    # Get the clean listing ID (folder name) instead of hash
    clean_listing_id = os.path.basename(folder)
    
    # Prepare bilingual features from localized data
    bilingual_features_dict = {'ro': {}, 'ru': {}}
    bilingual_amenities_dict = {'ro': {}, 'ru': {}}
    
    for lang_key in ['ro', 'ru']:
        if localized.get(lang_key):
            # Features
            lang_features = localized[lang_key].get('features', {})
            if isinstance(lang_features, str):
                try:
                    bilingual_features_dict[lang_key] = json.loads(lang_features)
                except:
                    bilingual_features_dict[lang_key] = {}
            else:
                bilingual_features_dict[lang_key] = lang_features or {}
            
            # Amenities
            lang_amenities = localized[lang_key].get('amenities', {})
            if isinstance(lang_amenities, str):
                try:
                    bilingual_amenities_dict[lang_key] = json.loads(lang_amenities)
                except:
                    bilingual_amenities_dict[lang_key] = {}
            else:
                bilingual_amenities_dict[lang_key] = lang_amenities or {}
    
    # Prepare Mainframe data structure
    mainframe_data = {
        'id': clean_listing_id,
        'url': data['url'],
        'domain': parsed.netloc,
        'template_name': template_name,  # Use the template passed to this function
        'title': data.get('title', ''),
        'description': data.get('description', ''),
        'price': data.get('price', {}),
        'address': data.get('address', ''),
        'display_address': data.get('display_address', data.get('address', '')),
        'geocoding_address': data.get('geocoding_address', data.get('address', '')),
        'contact': data.get('contact', ''),
        'images': data.get('images', []),
        'local_images': local_imgs,
        'features': bilingual_features_dict,
        'amenities': bilingual_amenities_dict,
        'standard_features': data.get('standard_features', {}),
        'map_data': data.get('map_data'),
        'localized': localized,
        'folder_path': folder,
        'status': 'active',
        'user_corrected_address': data.get('user_corrected_address', False)
    }
    
    # Save to Mainframe (silently - will be shown in completion message)
    mainframe_save_success = False
    try:
        mainframe_save_success = save_listing_to_mainframe(mainframe_data)
        if not mainframe_save_success:
            log_warning(f"Failed to save listing {clean_listing_id} to Mainframe.db")
    except Exception as e:
        log_warning(f"Error saving to Mainframe.db: {e}")
        import traceback
        traceback.print_exc()
    
    # Save POI data to Mainframe database
    if poi_data and mainframe_save_success:
        try:
            from Helper.database import save_poi_data_to_mainframe
            poi_save_success = save_poi_data_to_mainframe(clean_listing_id, poi_data, radius=500)
            if not poi_save_success:
                print("⚠️ Warning: Failed to save POI data to database")
        except Exception as e:
            print(f"⚠️ Warning: Error saving POI data: {e}")
    # ============================================================================
    # Generate HTML using new universal builder system
    # ============================================================================    
    try:
        from Helper.builder import build_listing_html
        from pathlib import Path
        
        # Build HTML using the new universal builder
        # It will automatically use the template specified in mainframe_data['template_name']
        html = build_listing_html(
            listing_id=clean_listing_id,
            template_name=mainframe_data.get('template_name', 'luna'),
            base_url=BASE_URL,
            save_to_file=True,
            output_path=Path(folder) / 'index.html'
        )
        
        if not html:
            raise RuntimeError("Failed to generate HTML - universal builder returned None")
        
        # log_success(f"Generated HTML with {mainframe_data.get('template_name', 'luna')} template")
    
    except Exception as e:
        log_error(f"❌ Error generating HTML: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # Generate PWA manifest for this listing
    try:
        # Prepare listing data for PWA manifest
        # listing_id is already clean from folder creation above
        clean_listing_id = os.path.basename(folder)
        pwa_data = {
            'id': clean_listing_id,
            'title': data.get('title', 'Property Listing'),
            'description': data.get('description', 'Real estate property listing'),
            'price': ' '.join(data.get('price', {}).values()) if data.get('price') else '',
            'location': data.get('address', ''),
            'type': 'apartment',  # Default type, could be enhanced with property type detection
            'images': [os.path.basename(img) for img in local_imgs] if local_imgs else [],
            'coordinates': [data.get('map_data', {}).get('lat'), data.get('map_data', {}).get('lng')] if data.get('map_data') else None,
            'phone': data.get('contact', ''),
            'timestamp': data.get('timestamp', ''),
            'lang': data.get('initial_lang', 'ro')
        }
        
        # Generate and save PWA manifest
        manifest_path = create_pwa_manifest(pwa_data, folder, BASE_URL)
        
    except Exception as e:
        log_info(f"Warning: Failed to generate PWA manifest: {e}")
        # Continue without PWA manifest - not critical for basic functionality
    
    # Return the listing ID for completion message
    return listing_id

def extract_domain_from_url(url):
    """Extract domain name from URL for template folder matching."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception as e:
        log_warning(f"Failed to parse URL {url}: {e}")
        return None

def find_domain_templates(domain, templates_dir):
    """Find templates in domain-specific folder."""
    if not domain:
        return []
    
    domain_folder = os.path.join(templates_dir, domain)
    if not os.path.isdir(domain_folder):
        return []
    
    # Exclude dashboard.html (used by Flask dashboard, not for scraping)
    templates = [f for f in os.listdir(domain_folder) 
                 if f.lower().endswith('.html') and f.lower() != 'dashboard.html']
    return [(os.path.join(domain_folder, tpl), f"{domain}/{tpl}", tpl) for tpl in templates]

def get_all_available_templates(templates_dir):
    """Get all templates from ALL subdirectories in Templates folder."""
    all_templates = []
    
    # Scan all subdirectories
    try:
        for item in os.listdir(templates_dir):
            item_path = os.path.join(templates_dir, item)
            
            # Check if it's a directory
            if os.path.isdir(item_path):
                # Find all .html files in this subdirectory (exclude dashboard.html)
                for file in os.listdir(item_path):
                    if file.lower().endswith('.html') and file.lower() != 'dashboard.html':
                        full_path = os.path.join(item_path, file)
                        display_name = f"{item}/{file}"
                        all_templates.append((full_path, display_name, file))
            
            # Also check root Templates folder for any HTML files (exclude dashboard.html)
            elif item.lower().endswith('.html') and item.lower() != 'dashboard.html':
                full_path = os.path.join(templates_dir, item)
                all_templates.append((full_path, item, item))
    
    except Exception as e:
        log_warning(f"Error scanning templates directory: {e}")
    
    return all_templates

def select_template_interactive(domain_templates, general_templates, domain):
    """Interactive template selection with all available templates."""
    print()
    print("="*50)
    print(f"   📋 Template Selection")
    print("="*50)
    
    all_options = []
    
    # Create sheet-style header with proper width
    print()
    print("╔═════╦═══════════════════════════════════════════╗")
    print("║ No. ║ Template                                  ║")
    print("╠═════╬═══════════════════════════════════════════╣")
    
    # Show domain-specific templates first if available
    if domain_templates:
        print(f"║     ║ ⭐ Recommended for {domain:<20} ║")
        print("╟─────╫───────────────────────────────────────────╢")
        for i, (full_path, display_name, file_name) in enumerate(domain_templates, 1):
            # Extract folder name and filename without extension
            folder_name = os.path.dirname(display_name).split('/')[-1] if '/' in display_name else ''
            file_base = os.path.splitext(os.path.basename(display_name))[0]
            short_display = folder_name if folder_name else file_base
            print(f"║ {i:2d}  ║ {short_display:<42} ║")
            all_options.append((full_path, display_name, "domain"))
            # Add separator line between entries (not after last entry in section)
            if i < len(domain_templates):
                print("╟─────╫───────────────────────────────────────────╢")
        
        # Add section separator between domain and general templates
        if general_templates:
            print("╠═════╬═══════════════════════════════════════════╣")
            print("║     ║ 📁 All Available Templates                ║")
            print("╟─────╫───────────────────────────────────────────╢")
    
    # Show all other templates
    if general_templates:
        start_idx = len(all_options) + 1
        for i, (full_path, display_name, file_name) in enumerate(general_templates, start_idx):
            # Extract folder name and filename without extension
            folder_name = os.path.dirname(display_name).split('/')[-1] if '/' in display_name else ''
            file_base = os.path.splitext(os.path.basename(display_name))[0]
            short_display = folder_name if folder_name else file_base
            print(f"║ {i:2d}  ║ {short_display:<42}║")
            all_options.append((full_path, display_name, "general"))
            # Add separator line between entries (not after last entry in section)
            if i < start_idx + len(general_templates) - 1:
                print("╟─────╫───────────────────────────────────────────╢")
    
    print("╚═════╩═══════════════════════════════════════════╝")
    print()
    
    if not all_options:
        log_warning("No templates found in Templates/ folder!")
        log_info("Please add template HTML files to Templates/ subdirectories.")
        return None
    
    # Show recommended template info
    if domain_templates:
        print(f"💡 Tip: Option 1 is recommended for {domain} listings")
    
    choice = input(f"Select template (1–{len(all_options)}, default 1): ").strip()
    
    try:
        idx = int(choice) if choice.isdigit() and 1 <= int(choice) <= len(all_options) else 1
        selected = all_options[idx-1]
        template_path, template_name, template_type = selected
        
        return template_path
    except (ValueError, IndexError):
        log_warning("Invalid selection, using first available template")
        return all_options[0][0]

# --- Main (template selection) ---
async def main():
    global TEMPLATE_PATH

    # Setup templates directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tpl_dir = os.path.join(script_dir, TEMPLATES_DIR)
    if not os.path.isdir(tpl_dir):
        os.makedirs(tpl_dir)
        print(f"Created '{TEMPLATES_DIR}/'—drop your *.html templates in there and rerun.")
        sys.exit(0)

    # Preemptively initialize Playwright for faster processing
    playwright_instance = None
    browser_instance = None
    if async_playwright:
        try:
            playwright_instance = await async_playwright().start()
            browser_instance = await playwright_instance.chromium.launch(headless=True)
        except Exception as e:
            log_warning(f"Failed to initialize Playwright: {e}")
            playwright_instance = None
            browser_instance = None

    # Get URL and determine domain
    print("="*50)
    print("   🏠 RealAgent - Real Estate Scraper")
    print("="*50)
    
    raw = input("\n🔗 Enter listing URL: ").strip()
    if not raw:
        print("❌ No URL provided.")
        return
    
    # Process single URL
    urls = [raw]
    domain = extract_domain_from_url(raw)
    
    if domain:
        # Look for domain-specific templates
        domain_templates = find_domain_templates(domain, tpl_dir)
        general_templates = get_all_available_templates(tpl_dir)
        
        # Interactive template selection
        TEMPLATE_PATH = select_template_interactive(domain_templates, general_templates, domain)
        
        if not TEMPLATE_PATH:
            print("No templates available. Please add templates and try again.")
            return
            
    else:
        # Fallback to original template selection if domain extraction fails
        log_warning("Could not extract domain from URL, using general template selection")
        
        # Exclude dashboard.html from template selection
        templates = [f for f in os.listdir(tpl_dir) 
                     if f.lower().endswith('.html') and f.lower() != 'dashboard.html']
        if not templates:
            print(f"No .html files found in '{TEMPLATES_DIR}/'. Add at least one and rerun.")
            return

        print("Available templates:")
        for i, tpl in enumerate(templates, 1):
            print(f"  {i}) {tpl}")
        choice = input(f"Select template (1–{len(templates)}, default 1): ").strip()
        idx = int(choice) if choice.isdigit() and 1 <= int(choice) <= len(templates) else 1
        TEMPLATE_PATH = os.path.join(tpl_dir, templates[idx-1])

    # Extract template name from TEMPLATE_PATH
    # Templates are named like: Luna.html, Thunder.html, etc.
    # We need to extract just the name part (luna, thunder, etc.)
    template_filename = os.path.basename(TEMPLATE_PATH)
    template_name = os.path.splitext(template_filename)[0].lower()
    
    # Process the listing
    print("\n" + "="*50)
    print("   🚀 Processing listing...")
    print("="*50)
    print()
    
    try:
        # Process listing and get ID for completion message
        listing_id = await process_listing(urls[0], browser_instance, template_name=template_name)

        print("="*50)
        print(f"✅  Listing {listing_id} processed successfully!")
        print("="*50)
        print()
    finally:
        # Clean up Playwright resources
        if browser_instance:
            await browser_instance.close()
        if playwright_instance:
            await playwright_instance.stop()
    
if __name__ == '__main__':
    asyncio.run(main())
