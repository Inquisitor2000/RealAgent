"""
Luna Template Builder
====================
Generates Luna-specific HTML blocks from universal data.

This builder takes data from Mainframe.db and creates HTML blocks
styled specifically for the Luna template design.
"""

import json
import html
from pathlib import Path
from typing import Dict, Any, Optional


def build_carousel_luna(images: list, local_images: list) -> str:
    """
    Generate image carousel HTML for Luna template.
    Luna uses a card-based carousel with dots navigation.
    
    Args:
        images: List of original image URLs
        local_images: List of local image paths (e.g., 'images/0.webp')
        
    Returns:
        HTML string for carousel slides
    """
    if not local_images and not images:
        return '<div class="slide"><div class="no-images">No images available</div></div>'
    
    # Use local images if available, otherwise URLs
    image_list = local_images if local_images else images
    
    html_parts = []
    
    for idx, img_path in enumerate(image_list):
        # Ensure path is relative
        if img_path.startswith('images/'):
            src = img_path
        elif '/' in img_path or '\\' in img_path:
            # Extract just the filename
            src = f"images/{Path(img_path).name}"
        else:
            src = img_path
        
        # Luna template expects .slide class
        html_parts.append(f'''
    <div class="slide">
      <img src="{html.escape(src)}" alt="Property image {idx + 1}" loading="lazy">
    </div>''')
    
    return '\n'.join(html_parts)


def build_combined_features_block_luna(features: Dict, amenities: Dict, lang: str = 'ro') -> str:
    """
    Build combined features and amenities block for Luna template.
    Luna style: One card with features list + collapsible amenities.
    
    Args:
        features: Bilingual features dict {'ro': {...}, 'ru': {...}}
        amenities: Bilingual amenities dict {'ro': {...}, 'ru': {...}}
        lang: Language ('ro' or 'ru')
        
    Returns:
        Combined HTML block with Luna-specific styling
    """
    lang_features = features.get(lang, {})
    lang_amenities = amenities.get(lang, {})
    
    # If neither features nor amenities exist, return empty
    if not lang_features and not lang_amenities:
        return ''
    
    html_parts = []
    html_parts.append('<div class="content-card">')
    html_parts.append('  <div class="property-info-card">')
    
    # Add features if available
    if lang_features:
        html_parts.append('    <h2>Caracteristici</h2>' if lang == 'ro' else '    <h2>Характеристики</h2>')
        
        for section, items in lang_features.items():
            # Skip adding <h3> if section name is the same as main heading (Caracteristici/Характеристики)
            if section not in ['Caracteristici', 'Характеристики']:
                html_parts.append(f'    <h3>{html.escape(str(section))}</h3>')
            html_parts.append('    <ul class="features-list">')
            
            if isinstance(items, dict):
                for key, value in items.items():
                    html_parts.append(f'''
      <li>
        <span class="feature-key">{html.escape(str(key))}</span>
        <span class="feature-value">{html.escape(str(value))}</span>
      </li>''')
            elif isinstance(items, list):
                for item in items:
                    html_parts.append(f'      <li><span class="feature-value">{html.escape(str(item))}</span></li>')
            
            html_parts.append('    </ul>')
    
    # Add amenities if available (in the SAME card) - COLLAPSIBLE
    if lang_amenities:
        amenities_title = 'Amenități' if lang == 'ro' else 'Удобства'
        html_parts.append(f'''
    <details class="amenities-spoiler" style="margin-top: 1rem;">
      <summary style="cursor: pointer; font-size: 1rem; font-weight: 400; color: var(--text); list-style: none; display: flex; align-items: center; padding: 0.5rem 0;">
        <span class="spoiler-icon" style="margin-right: 0.5rem; transition: transform 0.2s;">▶</span>
        {amenities_title}
      </summary>
      <ul class="features-list" style="margin-top: 0.5rem;">''')
        
        for key, value in lang_amenities.items():
            # Show amenity without checkmark for truthy values
            if value and str(value) != 'Nu' and str(value) != 'No' and str(value).lower() != 'false':
                html_parts.append(f'''
        <li><span class="feature-value">{html.escape(str(key))}</span></li>''')
        
        html_parts.append('      </ul>')
        html_parts.append('    </details>')
    
    html_parts.append('  </div>')
    html_parts.append('</div>')
    return '\n'.join(html_parts)


def build_luna_placeholders(listing_data: Dict[str, Any], base_url: str = '', include_pois: bool = False) -> Dict[str, Any]:
    """
    Build all Luna-specific placeholder values from listing data.
    
    This function takes raw data from Mainframe.db and generates
    Luna-styled HTML blocks for all template placeholders.
    
    Args:
        listing_data: Raw listing data from database
        base_url: Base URL for absolute paths (e.g., 'https://example.com')
        include_pois: Whether to fetch and include POI data
        
    Returns:
        Dictionary with all Luna-specific placeholder values
    """
    # Start with listing data
    placeholders = dict(listing_data)
    
    # Add template metadata
    placeholders['template_name'] = 'luna'
    placeholders['listing_id'] = listing_data.get('id', 'unknown')
    
    # Determine primary language
    html_lang = 'ro'  # Default
    if listing_data.get('url', '').find('/ru/') > 0:
        html_lang = 'ru'
    placeholders['html_lang'] = html_lang
    
    # Build Luna-specific HTML blocks
    images = listing_data.get('images', [])
    local_images = listing_data.get('local_images', [])
    placeholders['slides'] = build_carousel_luna(images, local_images)
    
    features = listing_data.get('features', {})
    amenities = listing_data.get('amenities', {})
    placeholders['combined_features_block_ro'] = build_combined_features_block_luna(features, amenities, 'ro')
    placeholders['combined_features_block_ru'] = build_combined_features_block_luna(features, amenities, 'ru')
    
    # Map data
    map_data = listing_data.get('map_data', {})
    if map_data:
        placeholders['map_lat'] = map_data.get('lat', 47.0105)
        placeholders['map_lng'] = map_data.get('lng', 28.8638)
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
    
    # Address - Format for multilingual display
    # Use geocoding_address (with building numbers) if available, fallback to address
    address = listing_data.get('geocoding_address', listing_data.get('address', 'N/A'))
    placeholders['address'] = address  # Keep original for compatibility
    
    # Check if this is a user-corrected address (from geoguess helper)
    # User-corrected addresses should be preserved as-is without re-formatting
    is_user_corrected = bool(listing_data.get('user_corrected_address', 0))
    
    if is_user_corrected:
        # Preserve user-corrected address exactly as provided
        placeholders['address_ro'] = address
        placeholders['address_ru'] = address
    else:
        # Format address for proper Romanian/Russian display (only for scraped addresses)
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
    
    # Labels (Luna uses default Romanian/Russian labels)
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
                placeholders['poi_data_script'] = f'''
    <script>
      // Pre-generated POI data - eliminates runtime API calls
      window.preGeneratedPOIData = {poi_json};
      console.log('✅ Loaded pre-generated POI data:', Object.keys(window.preGeneratedPOIData));
    </script>'''
            else:
                placeholders['poi_data_script'] = '''
    <script>
      // No POI data available for this listing
      window.preGeneratedPOIData = {};
      console.log('⚠️ No pre-generated POI data available');
    </script>'''
        except Exception as e:
            print(f"⚠️ Warning: Failed to load POI data for template: {e}")
            placeholders['poi_data_script'] = '''
    <script>
      // Failed to load POI data
      window.preGeneratedPOIData = {};
      console.log('❌ Failed to load pre-generated POI data');
    </script>'''
    else:
        placeholders['poi_data_script'] = '''
    <script>
      // POI data disabled
      window.preGeneratedPOIData = {};
    </script>'''
    
    return placeholders


def build_luna_html(listing_id: str, template_path: str, base_url: str = '', include_pois: bool = True) -> Optional[str]:
    """
    Build complete Luna HTML from Mainframe.db data.
    
    Args:
        listing_id: Listing ID to build HTML for
        template_path: Path to Luna.html template file
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
    placeholders = build_luna_placeholders(listing_data, base_url, include_pois=include_pois)
    
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
        template = template.replace(placeholder, str(value))
    
    return template
