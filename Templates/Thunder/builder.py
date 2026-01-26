"""
Thunder Template Builder
========================
Generates Thunder-specific HTML blocks from universal data.

This builder takes data from Mainframe.db and creates HTML blocks
styled specifically for the Thunder template's Tinder-style swipe design.
"""

import json
import html
import re
from pathlib import Path
from typing import Dict, Any, Optional


def build_card_data_thunder(images: list, local_images: list, title: str = '', price: str = '', address: str = '', 
                            description_ro: str = '', description_ru: str = '', contact_ro: str = '', contact_ru: str = '',
                            contact_clean: str = '', contact_label_ro: str = '', contact_label_ru: str = '',
                            features_ro_html: str = '', features_ru_html: str = '') -> str:
    """
    Generate card data as JSON for Thunder template (single-card Tinder-style).
    
    Args:
        images: List of original image URLs
        local_images: List of local image paths
        title: Property title
        price: Property price
        address: Property address
        description_ro/ru: Descriptions in Romanian/Russian
        contact_ro/ru: Contact numbers
        contact_clean: Cleaned contact for tel: links
        contact_label_ro/ru: Contact labels
        features_ro_html/ru_html: Features HTML blocks
        
    Returns:
        JSON string with all card data
    """
    if not local_images and not images:
        local_images = []
    
    # Use local images if available, otherwise URLs
    image_list = local_images if local_images else images
    
    cards = []
    
    # Add image cards (with description data for overlay)
    for idx, img_path in enumerate(image_list):
        # Ensure path is relative
        if img_path.startswith('images/'):
            src = img_path
        elif '/' in img_path or '\\' in img_path:
            src = f"images/{Path(img_path).name}"
        else:
            src = img_path
        
        cards.append({
            'type': 'image',
            'image': src,
            'title': title,
            'price': price,
            'address': address,
            'label_ro': 'Descriere',
            'label_ru': 'Описание',
            'text_ro': description_ro,
            'text_ru': description_ru,
            'contact_label_ro': contact_label_ro,
            'contact_label_ru': contact_label_ru,
            'contact_ro': contact_ro,
            'contact_ru': contact_ru,
            'contact_clean': contact_clean
        })
    
    # Add features card
    cards.append({
        'type': 'features',
        'content_ro': features_ro_html,
        'content_ru': features_ru_html
    })
    
    return json.dumps(cards, ensure_ascii=False)


def build_features_block_thunder(features: Dict, amenities: Dict, lang: str = 'ro') -> str:
    """
    Build features block for Thunder template.
    Thunder style: Clean list format with key-value pairs.
    
    Args:
        features: Bilingual features dict {'ro': {...}, 'ru': {...}}
        amenities: Bilingual amenities dict {'ro': {...}, 'ru': {...}}
        lang: Language ('ro' or 'ru')
        
    Returns:
        Features HTML block with Thunder-specific styling
    """
    lang_features = features.get(lang, {})
    lang_amenities = amenities.get(lang, {})
    
    # If neither features nor amenities exist, return empty
    if not lang_features and not lang_amenities:
        return ''
    
    html_parts = []
    
    # Add features if available
    if lang_features:
        html_parts.append('<h2>Caracteristici</h2>' if lang == 'ro' else '<h2>Характеристики</h2>')
        
        for section, items in lang_features.items():
            # Skip adding <h3> if section name is the same as main heading
            if section not in ['Caracteristici', 'Характеристики']:
                html_parts.append(f'<h3>{html.escape(str(section))}</h3>')
            
            html_parts.append('<ul class="features-list">')
            
            if isinstance(items, dict):
                for key, value in items.items():
                    html_parts.append(f'<li><span class="feature-key">{html.escape(str(key))}</span><span class="feature-value">{html.escape(str(value))}</span></li>')
            elif isinstance(items, list):
                for item in items:
                    html_parts.append(f'<li><span class="feature-value">{html.escape(str(item))}</span></li>')
            
            html_parts.append('</ul>')
    
    # Add amenities if available (collapsible)
    if lang_amenities:
        amenities_title = 'Amenități' if lang == 'ro' else 'Удобства'
        html_parts.append(f'<details class="amenities-spoiler"><summary style="cursor: pointer; list-style: none; display: flex; align-items: center; padding: 0.5rem 0;"><span class="spoiler-icon" style="margin-right: 0.5rem; transition: transform 0.2s;">▶</span>{amenities_title}</summary><ul class="features-list">')
        
        for key, value in lang_amenities.items():
            # Show amenity for truthy values
            if value and str(value) != 'Nu' and str(value) != 'No' and str(value).lower() != 'false':
                html_parts.append(f'<li><span class="feature-value">{html.escape(str(key))}</span></li>')
        
        html_parts.append('</ul></details>')
    
    return '\n'.join(html_parts)


def build_thunder_placeholders(listing_data: Dict[str, Any], base_url: str = '', include_pois: bool = False) -> Dict[str, Any]:
    """
    Build all Thunder-specific placeholder values from listing data.
    
    This function takes raw data from Mainframe.db and generates
    Thunder-styled HTML blocks for all template placeholders.
    
    Args:
        listing_data: Raw listing data from database
        base_url: Base URL for absolute paths (e.g., 'https://example.com')
        include_pois: Whether to fetch and include POI data
        
    Returns:
        Dictionary with all Thunder-specific placeholder values
    """
    # Start with listing data
    placeholders = dict(listing_data)
    
    # Add template metadata
    placeholders['template_name'] = 'thunder'
    placeholders['listing_id'] = listing_data.get('id', 'unknown')
    
    # Determine primary language
    html_lang = 'ro'  # Default
    if listing_data.get('url', '').find('/ru/') > 0:
        html_lang = 'ru'
    placeholders['html_lang'] = html_lang
    
    # Build Thunder-specific HTML blocks
    images = listing_data.get('images', [])
    local_images = listing_data.get('local_images', [])
    title = listing_data.get('title_ro', 'Proprietate')
    price = listing_data.get('price', 'Preț la cerere') if isinstance(listing_data.get('price'), str) else ', '.join([str(v) for v in listing_data.get('price', {}).values()])
    address = listing_data.get('geocoding_address', listing_data.get('address', 'N/A'))
    
    # Build features blocks
    features = listing_data.get('features', {})
    amenities = listing_data.get('amenities', {})
    features_ro_html = build_features_block_thunder(features, amenities, 'ro')
    features_ru_html = build_features_block_thunder(features, amenities, 'ru')
    
    # Contact data
    contact = listing_data.get('contact', 'N/A')
    contact_clean = contact.replace(' ', '').replace('-', '')
    
    # Generate card data as JSON
    card_data_json = build_card_data_thunder(
        images, local_images, title, price, address,
        description_ro=listing_data.get('description_ro', ''),
        description_ru=listing_data.get('description_ru', ''),
        contact_ro=contact,
        contact_ru=contact,
        contact_clean=contact_clean,
        contact_label_ro='Contact',
        contact_label_ru='Контакты',
        features_ro_html=features_ro_html,
        features_ru_html=features_ru_html
    )
    placeholders['card_data_json'] = card_data_json
    
    features = listing_data.get('features', {})
    amenities = listing_data.get('amenities', {})
    placeholders['combined_features_block_ro'] = build_features_block_thunder(features, amenities, 'ro')
    placeholders['combined_features_block_ru'] = build_features_block_thunder(features, amenities, 'ru')
    
    # Map data
    map_data = listing_data.get('map_data', {})
    if map_data:
        try:
            placeholders['map_lat'] = float(map_data.get('lat', 47.0105))
            placeholders['map_lng'] = float(map_data.get('lng', 28.8638))
        except (ValueError, TypeError):
            placeholders['map_lat'] = 47.0105
            placeholders['map_lng'] = 28.8638
        placeholders['map_title'] = map_data.get('title', '')
        placeholders['map_data'] = json.dumps(map_data)
    else:
        placeholders['map_lat'] = 47.0105
        placeholders['map_lng'] = 28.8638
        placeholders['map_title'] = ''
        placeholders['map_data'] = '{}'
    
    # Price formatting
    price_data = listing_data.get('price', {})
    if isinstance(price_data, str):
        try:
            price_data = json.loads(price_data)
        except:
            pass
    
    if price_data and isinstance(price_data, dict):
        price_str = ', '.join([str(v) for v in price_data.values()])
    else:
        price_str = 'Preț la cerere' if html_lang == 'ro' else 'Цена по запросу'
    
    placeholders['price'] = price_str
    placeholders['price_ro'] = price_str
    placeholders['price_ru'] = price_str
    
    # Contact formatting
    contact = listing_data.get('contact', 'N/A')
    contact_clean = contact.replace(' ', '').replace('-', '')
    
    placeholders['contact'] = contact
    placeholders['contact_ro'] = contact
    placeholders['contact_ru'] = contact
    placeholders['contact_clean'] = contact_clean
    placeholders['contact_clean_ro'] = contact_clean
    placeholders['contact_clean_ru'] = contact_clean
    
    # Bilingual content
    placeholders['title'] = listing_data.get('title_ro', 'Proprietate')
    placeholders['title_ro'] = listing_data.get('title_ro', 'Proprietate')
    placeholders['title_ru'] = listing_data.get('title_ru', 'Недвижимость')
    
    placeholders['description'] = listing_data.get('description_ro', '')
    placeholders['description_ro'] = listing_data.get('description_ro', '')
    placeholders['description_ru'] = listing_data.get('description_ru', '')
    
    # Meta description (clean, max 160 chars)
    desc_meta = listing_data.get('description_ro', '')[:157] + '...' if len(listing_data.get('description_ro', '')) > 160 else listing_data.get('description_ro', '')
    placeholders['description_meta'] = desc_meta.replace('\n', ' ')
    
    # Address
    address = listing_data.get('geocoding_address', listing_data.get('address', 'N/A'))
    placeholders['address'] = address
    
    # Check if this is a user-corrected address
    is_user_corrected = bool(listing_data.get('user_corrected_address', 0))
    
    if is_user_corrected:
        # Preserve user-corrected address exactly as provided
        placeholders['address_ro'] = address
        placeholders['address_ru'] = address
    else:
        # Format address for proper Romanian/Russian display
        try:
            from Helper.address_formatter import format_address_for_display
            formatted_addresses = format_address_for_display(address)
            placeholders['address_ro'] = formatted_addresses.get('ro', address)
            placeholders['address_ru'] = formatted_addresses.get('ru', address)
        except Exception as e:
            # Fallback to original address if formatting fails
            print(f"Warning: Address formatting failed: {e}")
            placeholders['address_ro'] = address
            placeholders['address_ru'] = address
    
    # Labels (Thunder uses default Romanian/Russian labels)
    placeholders['contact_label_ro'] = 'Contact'
    placeholders['contact_label_ru'] = 'Контакты'
    placeholders['description_label_ro'] = 'Descriere'
    placeholders['description_label_ru'] = 'Описание'
    placeholders['location_label_ro'] = 'Locație'
    placeholders['location_label_ru'] = 'Местоположение'
    placeholders['features_label_ro'] = 'Caracteristici'
    placeholders['features_label_ru'] = 'Характеристики'
    placeholders['price_label_ro'] = 'Preț'
    placeholders['price_label_ru'] = 'Цена'
    
    # SEO / Social
    placeholders['og_locale'] = 'ro_RO' if html_lang == 'ro' else 'ru_RU'
    placeholders['current_url'] = f"{base_url}/{listing_data.get('id', '')}" if base_url else ''
    
    # Share image (first image if available)
    if local_images:
        first_image = local_images[0]
        placeholders['share_image_url'] = f"{base_url}/{listing_data.get('id', '')}/{first_image}" if base_url else first_image
    else:
        placeholders['share_image_url'] = ''
    
    # PWA
    placeholders['vapid_public_key'] = ''  # TODO: Add actual VAPID key
    
    # POI Data - embed pre-generated POI data if available
    if include_pois:
        try:
            from Helper.database import get_poi_data_from_mainframe
            poi_data = get_poi_data_from_mainframe(listing_data.get('id', ''))
            
            if poi_data:
                # Create JavaScript object with POI data
                poi_json = json.dumps(poi_data, ensure_ascii=False, indent=2)
                placeholders['poi_data_script'] = f'<script>\n  // Pre-generated POI data - eliminates runtime API calls\n  window.preGeneratedPOIData = {poi_json};\n  console.log("✅ Loaded pre-generated POI data:", Object.keys(window.preGeneratedPOIData));\n</script>'
            else:
                placeholders['poi_data_script'] = '<script>\n  // No POI data available for this listing\n  window.preGeneratedPOIData = {};\n  console.log("⚠️ No pre-generated POI data available");\n</script>'
        except Exception as e:
            print(f"⚠️ Warning: Failed to load POI data for template: {e}")
            placeholders['poi_data_script'] = '<script>\n  // Failed to load POI data\n  window.preGeneratedPOIData = {};\n  console.log("❌ Failed to load pre-generated POI data");\n</script>'
    else:
        placeholders['poi_data_script'] = '<script>\n  // POI data disabled\n  window.preGeneratedPOIData = {};\n</script>'
    
    return placeholders


def build_thunder_html(listing_id: str, template_path: str, base_url: str = '', include_pois: bool = True) -> Optional[str]:
    """
    Build complete Thunder HTML from Mainframe.db data.
    
    Args:
        listing_id: Listing ID to build HTML for
        template_path: Path to Thunder.html template file
        base_url: Base URL for absolute paths
        include_pois: Whether to fetch and embed POI data (default: True)
        
    Returns:
        Complete HTML string, or None if listing not found
    """
    from Helper.database import get_listing_from_mainframe
    
    # Get listing data
    listing_data = get_listing_from_mainframe(listing_id)
    if not listing_data:
        print(f"❌ Listing {listing_id} not found in Mainframe.db")
        return None
    
    # Build all placeholders
    placeholders = build_thunder_placeholders(listing_data, base_url, include_pois=include_pois)
    
    # Load template
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    except Exception as e:
        print(f"❌ Error reading template {template_path}: {e}")
        return None
    
    # Replace all placeholders
    for key, value in placeholders.items():
        placeholder = f'{{{key}}}'
        
        # Skip if placeholder not in template
        if placeholder not in template:
            continue
        
        # Handle different value types appropriately
        if isinstance(value, (int, float)):
            # Numbers should not be quoted
            replacement = str(value)
        elif isinstance(value, bool):
            # Booleans should be lowercase
            replacement = 'true' if value else 'false'
        elif value is None:
            # None becomes null in JavaScript
            replacement = 'null'
        elif isinstance(value, str):
            # For strings in JavaScript context, check if it's already JSON/HTML/markup
            # These should NOT be escaped
            if (value.startswith('{') or value.startswith('[') or value.startswith('<') or 
                value.startswith('\n') or value.startswith('\r') or 
                '<' in value or '\n' in value):
                # Already formatted (JSON, HTML, etc.) - use as-is
                replacement = value
            else:
                # Regular string - escape for JavaScript (only for plain text)
                replacement = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
        else:
            # Other types - convert to string
            replacement = str(value)
        
        template = template.replace(placeholder, replacement)
    
    return template
