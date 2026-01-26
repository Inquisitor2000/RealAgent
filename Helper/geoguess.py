"""
GeoGuess Helper Module
Contains address parsing and translation utilities for geocoding.
"""

import re
from urllib.parse import quote


def detect_cyrillic_text(text):
    """Detect if text contains Cyrillic characters (Russian)."""
    if not text:
        return False
    # Check for Cyrillic Unicode range
    cyrillic_pattern = re.compile(r'[\u0400-\u04FF]')
    return bool(cyrillic_pattern.search(text))


def translate_russian_to_romanian(text, street_translations):
    """Translate Russian street names and districts to Romanian equivalents.
    
    Args:
        text: Text to translate
        street_translations: Dictionary of Russian to Romanian translations
    
    Returns:
        Translated text
    """
    if not text or not detect_cyrillic_text(text):
        return text
    
    translated = text
    
    # Sort translations by length (longest first) to handle multi-word phrases correctly
    sorted_translations = sorted(street_translations.items(), key=lambda x: len(x[0]), reverse=True)
    
    # Apply translations (case-insensitive) with multiple passes
    for russian, romanian in sorted_translations:
        if russian.lower() in translated.lower():
            # Create pattern that matches the Russian text
            pattern = re.compile(re.escape(russian), re.IGNORECASE)
            old_translated = translated
            translated = pattern.sub(romanian, translated)
            if old_translated != translated:
                print(f"🔍 Translated '{russian}' → '{romanian}'")
    
    # Second pass: ensure all remaining Cyrillic words are handled
    # Split by common delimiters and translate remaining Cyrillic words
    words = re.split(r'([,\s\.\-]+)', translated)
    final_words = []
    
    for word in words:
        if word and detect_cyrillic_text(word):
            # Try to find translation for this specific word
            word_clean = word.strip(r'.,\-\s')
            translated_word = word
            
            for russian, romanian in sorted_translations:
                if russian.lower() == word_clean.lower():
                    # Preserve original punctuation and spacing
                    translated_word = word.replace(word_clean, romanian)
                    print(f"🔍 Word-level translation: '{word_clean}' → '{romanian}'")
                    break
            
            final_words.append(translated_word)
        else:
            final_words.append(word)
    
    return ''.join(final_words)


def parse_address_string(addr, show_table=False):
    """Parse a Moldovan address string into its components.
    
    Handles multiple formats:
    - City-first: "Chișinău mun., Chișinău, Botanica, Bd. Decebal, 23"
    - Street-first: "Strada Constantin Brâncuși 5, MD-2060, Chișinău, Moldova"
    - User-corrected: "Albisoara St 18, Chișinău, Moldova"
    
    Args:
        addr: Address string to parse
        show_table: Whether to display the debug table (default: True)
        
    Returns:
        Dictionary with parsed address components:
        - street: Full street part
        - street_name: Street name without prefix
        - district: District/neighborhood
        - building: Building/house number
        - full_street_with_building: Complete street with building
        - original_address: Original address string
        - was_translated: Boolean indicating if translation occurred
    """
    # No automatic translation - user will correct low-confidence addresses manually
    parts = [p.strip() for p in addr.split(',')]
    street, street_name, district, building, full_street_with_building = '', '', '', '', ''

    for i, part in enumerate(parts):
        # Define street prefixes (Romanian, Russian, and English)
        street_prefixes = [
            'str.', 'bd.', 'bdul.', 'strada', 'bulevardul', 'bulevardul.',
            'ул.', 'бул.', 'улица', 'бульвар', 'проспект', 'пр.',
            'st.', 'st ', 'street', 'avenue', 'ave', 'ave.', 'blvd', 'blvd.', 'road', 'rd', 'rd.'
        ]
        
        # Check if this part has a street prefix
        has_street_prefix = any(part.lower().startswith(prefix) or f' {prefix}' in part.lower() for prefix in street_prefixes)
        
        # Also check if this part looks like a street (contains word + number pattern)
        # This handles various user-corrected address formats:
        # - "Albisoara St 18" (suffix after name)
        # - "Constantin Brâncuși Street 5" (suffix in middle)
        # - "Decebal Blvd 23" (suffix in middle)
        street_pattern_suffix_after = re.match(r'^([A-Za-zĂÂÎȘȚăâîșțА-Яа-я\s]+)\s+(?:St\.?|Street|Str\.?|strada|ул\.?|Ave\.?|Avenue|Blvd\.?|Boulevard|Rd\.?|Road)\s+([\d]+[\w/-]*)$', part, re.IGNORECASE)
        street_pattern_suffix_before = re.match(r'^([A-Za-zĂÂÎȘȚăâîșțА-Яа-я\s]+(?:St\.?|Street|Str\.?|strada|ул\.?|Ave\.?|Avenue|Blvd\.?|Boulevard|Rd\.?|Road)?)\s+([\d]+[\w/-]*)$', part, re.IGNORECASE)
        street_pattern = street_pattern_suffix_after or street_pattern_suffix_before
        
        if has_street_prefix or street_pattern:
            street = part
            full_street_with_building = part
            
            # Try to extract street name and building number from the street part
            # Format: "Strada Name Number" or "Name St Number" or "Name Number"
            
            # First try: user-corrected format with street suffix (more specific pattern)
            # This handles: "Albisoara St 18", "Constantin Brâncuși Street 5", "Decebal Blvd 23"
            if street_pattern:
                street_name = street_pattern.group(1).strip()
                building = street_pattern.group(2).strip()
                full_street_with_building = part
                # Remove the abbreviation from street name if present
                street_name = re.sub(r'\s+(?:St\.?|Street|Str\.?|strada|ул\.?|Ave\.?|Avenue|Blvd\.?|Boulevard|Rd\.?|Road)\s*$', '', street_name, flags=re.IGNORECASE).strip()
            # Second try: standard prefix format (less specific, more general)
            # This handles: "Strada Albisoara 18", "ул. Албишоара 18"
            else:
                # Only match prefixes at the START of the string
                prefix_match = re.match(r'^(?:str\.|bd\.|bdul\.|strada|bulevardul\.?|ул\.|бул\.|улица|бульвар|проспект|пр\.)\s+(.+)', part, re.IGNORECASE)
                if prefix_match:
                    street_with_number = prefix_match.group(1).strip()
                    # Try to extract street name and building number
                    # Pattern: "Name Number" where number is at the end
                    # Supports: 18, 18A, 18/5, 18-A, etc.
                    number_match = re.search(r'(.+?)\s+([\d]+[\w/-]*)$', street_with_number, re.IGNORECASE)
                    if number_match:
                        street_name = number_match.group(1).strip()
                        building = number_match.group(2).strip()
                        full_street_with_building = part
                    else:
                        # No number found in the street part
                        street_name = street_with_number
                        full_street_with_building = part
            
            # Check if next part is a standalone building number
            if not building and i + 1 < len(parts) and re.match(r'^[\d]+[\w/-]*$', parts[i+1]):
                building = parts[i+1]
                full_street_with_building += f', {building}'
        elif 'mun.' not in part and part not in ['Chișinău', 'Moldova', 'Кишинэу', 'Кишинев', 'Молдова']:
            # Skip postal codes (format: MD-####)
            if re.match(r'^MD-?\d{4}$', part, re.IGNORECASE):
                continue
            # Standalone building number (supports: 18, 18A, 18/5, 18-B, etc.)
            if not building and re.match(r'^[\d]+[\w/-]*$', part):
                building = part
                if street:
                    full_street_with_building += f', {building}'
            elif not district:
                district = part
                
    # Clean street name by removing all prefixes directly
    clean_street_name = street_name
    prefixes_to_remove = [
        'str.', 'bd.', 'bdul.', 'strada', 'bulevardul', 'bulevardul.',
        'ул.', 'бул.', 'улица', 'бульвар', 'проспект', 'пр.',
        'st.', 'st ', 'street', 'avenue', 'ave', 'ave.', 'blvd', 'blvd.', 'road', 'rd', 'rd.'
    ]
    
    # Remove prefixes from street name (case-insensitive)
    for prefix in prefixes_to_remove:
        # Use regex for case-insensitive replacement
        clean_street_name = re.sub(r'\b' + re.escape(prefix) + r'\b', '', clean_street_name, flags=re.IGNORECASE).strip()
    
    # Clean up extra whitespace
    clean_street_name = re.sub(r'\s+', ' ', clean_street_name).strip()
    
    parsed_result = {
        'street': street,
        'street_name': clean_street_name,
        'district': district,
        'building': building,
        'full_street_with_building': full_street_with_building,
        'original_address': addr,  # Keep original for reference
        'was_translated': False  # No automatic translation - user will correct manually
    }
    
    # Debug logging for address parsing in table format (only if show_table=True)
    if show_table:
        print()
        print("╔═══════════╦═══════════════════════════════════════════════════╗")
        print("║ Field     ║ Value                                             ║")
        print("╠═══════════╬═══════════════════════════════════════════════════╣")
        
        # Truncate long values to fit in the table (48 chars visible + "...")
        max_width = 47
        addr_display = addr[:max_width] + "..." if len(addr) > max_width else addr
        street_display = street[:max_width] + "..." if len(street) > max_width else street
        district_display = district[:max_width] + "..." if len(district) > max_width else district
        building_display = building[:max_width] + "..." if len(building) > max_width else building
        
        print(f"║ Original  ║ {addr_display:<50}║")
        print("╟───────────╫───────────────────────────────────────────────────╢")
        print(f"║ Street    ║ {street_display:<50}║")
        print("╟───────────╫───────────────────────────────────────────────────╢")
        print(f"║ District  ║ {district_display:<50}║")
        print("╟───────────╫───────────────────────────────────────────────────╢")
        print(f"║ Building  ║ {building_display:<50}║")
        print("╚═══════════╩═══════════════════════════════════════════════════╝")
        print()
    
    return parsed_result


def build_geocode_queries(parsed, geocoding_address):
    """Build a prioritized list of geocoding search queries.
    
    Args:
        parsed: Dictionary from parse_address_string()
        geocoding_address: The address string to use for geocoding
        
    Returns:
        List of query strings to try in order
    """
    queries_detected = []
    queries_default = []

    # Detect target city directly (fallback to Chișinău if none detected)
    detected_city = 'Chișinău'
    try:
        # Define Moldovan cities directly
        city_names = ['chișinău', 'chisinau', 'bălți', 'balti', 'tiraspol', 'bender', 'tighina', 'cahul', 'ungheni', 'soroca', 'orhei', 'comrat']
        original_addr = (parsed.get('original_address') or '').lower()
        for cname in city_names:
            if cname and cname in original_addr:
                detected_city = cname.capitalize()
                break
        if detected_city.lower() in ['chisinau', 'кишинэу', 'кишинев']:
            detected_city = 'Chișinău'
    except Exception:
        pass

    # If address was translated from Russian, add both translated and original versions
    if parsed.get('was_translated', False):
        print(f"🔍 Building queries for translated Russian address...")

    # Build queries city-first, then street in that city
    street = parsed.get('street_name')
    building = parsed.get('building')
    district = parsed.get('district')

    # Phase 1: detected city - hierarchical approach: City → Street → Building
    # 1. Start with city to establish the area
    queries_detected.append(f"{detected_city}, Moldova")
    
    # 2. Then try street within that city
    if street:
        # Import street name translations
        from .translations import translate_street_name
        
        # Clean Russian street name for better matching
        clean_street = street.replace('ул.', '').replace('улица', '').strip()
        
        # Try transliterating Russian to Latin for better OpenStreetMap matching
        transliterated_street = translate_street_name(clean_street)
        
        if district:
            # Prioritize district-specific queries to avoid ambiguous street names
            queries_detected.append(f"bulevardul {transliterated_street}, {district}, {detected_city}, Moldova")
            queries_detected.append(f"strada {transliterated_street}, {district}, {detected_city}, Moldova")
            queries_detected.append(f"{transliterated_street}, {district}, {detected_city}, Moldova")
            queries_detected.append(f"bulevardul {clean_street}, {district}, {detected_city}, Moldova")
            queries_detected.append(f"strada {clean_street}, {district}, {detected_city}, Moldova")
            if parsed.get('was_translated'):
                queries_detected.append(f"{street}, sectorul {district}, {detected_city}")
                queries_detected.append(f"{street}, {district}, {detected_city}")
        
        # Non-district queries (lower priority to avoid wrong locations)
        queries_detected.append(f"bulevardul {transliterated_street}, {detected_city}, Moldova")
        queries_detected.append(f"strada {transliterated_street}, {detected_city}, Moldova")
        queries_detected.append(f"{transliterated_street}, {detected_city}, Moldova")
        queries_detected.append(f"bulevardul {clean_street}, {detected_city}, Moldova")
        queries_detected.append(f"strada {clean_street}, {detected_city}, Moldova")
        queries_detected.append(f"str. {clean_street}, {detected_city}, Moldova")
        # Also try original Russian format
        queries_detected.append(f"{street}, {detected_city}, Moldova")
    
    # 3. Finally, try specific building on that street
    if street and building:
        if district:
            queries_detected.append(f"{street} {building}, {district}, {detected_city}, Moldova")
        queries_detected.append(f"{street} {building}, {detected_city}, Moldova")
        queries_detected.append(f"strada {street} {building}, {detected_city}, Moldova")
        if parsed.get('was_translated'):
            queries_detected.append(f"str. {street} {building}, {detected_city}")
    
    if parsed.get('full_street_with_building'):
        queries_detected.append(f"{parsed.get('full_street_with_building')}, {detected_city}, Moldova")

    # Limit detected-city attempts to first 5 queries to allow timely fallback
    # But prioritize specific street queries over generic city query
    if len(queries_detected) > 5:
        # Keep city query first, then add most specific queries
        city_query = f"{detected_city}, Moldova"
        other_queries = [q for q in queries_detected if q != city_query]
        queries_detected = [city_query] + other_queries[:4]

    # Phase 2: default city (Chișinău) if different
    default_city = 'Chișinău'
    if default_city.lower() != (detected_city or '').lower():
        queries_default.append(f"{default_city}, Moldova")
        if street and building:
            if district:
                queries_default.append(f"{street} {building}, {district}, {default_city}, Moldova")
            queries_default.append(f"{street} {building}, {default_city}, Moldova")
            queries_default.append(f"strada {street} {building}, {default_city}, Moldova")
            if parsed.get('was_translated'):
                queries_default.append(f"str. {street} {building}, {default_city}")
        if street:
            if district:
                queries_default.append(f"strada {street}, {district}, {default_city}, Moldova")
            queries_default.append(f"strada {street}, {default_city}, Moldova")
        if parsed.get('full_street_with_building'):
            queries_default.append(f"{parsed.get('full_street_with_building')}, {default_city}, Moldova")

    # Always include the geocoding address (might be original Russian)
    tail = []
    tail.append(geocoding_address)
    if parsed.get('was_translated') and parsed.get('original_address'):
        tail.append(parsed.get('original_address'))
    tail.append(parsed.get('display_address', geocoding_address))  # Fallback

    # Merge while preserving order and uniqueness
    all_queries = list(dict.fromkeys(queries_detected + queries_default + tail))
    
    # PRIORITY FIX: Move building-specific queries to the front
    # This ensures building-level results are found before accepting street-level results
    building_queries = []
    other_queries = []
    
    building = parsed.get('building')
    if building:
        for query in all_queries:
            if building in query:
                building_queries.append(query)
            else:
                other_queries.append(query)
        
        # Put building queries first
        queries = building_queries + other_queries
    else:
        queries = all_queries

    if parsed.get('was_translated'):
        print(f"🔍 Generated {len(queries)} queries for translated address")

    return queries


def get_all_translations():
    """Get street and district translations from the translations module.
    
    Returns:
        Dictionary of Russian to Romanian translations
    """
    # Import here to avoid circular dependencies
    try:
        from .translations import PROPERTY_FEATURE_TRANSLATIONS
        return PROPERTY_FEATURE_TRANSLATIONS
    except ImportError:
        # Fallback to empty dictionary if translations module is not available
        print("⚠️  Warning: translations module not found")
        return {}
