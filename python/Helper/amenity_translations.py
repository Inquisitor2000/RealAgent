"""
Multi-language translation system for amenities and features.
Canonical language: English (stored in database)
Display languages: Romanian, Russian
"""

from typing import Dict, Optional

# ============================================================================
# AMENITIES - Canonical English keys with RO/RU translations
# ============================================================================
AMENITIES = {
    'furnished': {
        'en': 'Furnished',
        'ro': 'Mobilat',
        'ru': 'Меблирована'
    },
    'air_conditioning': {
        'en': 'Air Conditioning',
        'ro': 'Aparat de aer condiționat',
        'ru': 'Кондиционер'
    },
    'elevator': {
        'en': 'Elevator',
        'ro': 'Ascensor',
        'ru': 'Лифт'
    },
    'cable_tv': {
        'en': 'Cable TV',
        'ro': 'Cablu TV',
        'ru': 'ТВ кабель'
    },
    'appliances': {
        'en': 'With Appliances',
        'ro': 'Cu tehnică electrocasnică',
        'ru': 'С бытовой техникой'
    },
    'ready_to_move': {
        'en': 'Ready to Move In',
        'ro': 'Gata de mutat',
        'ru': 'Готова к въезду'
    },
    'double_glazed_windows': {
        'en': 'Double Glazed Windows',
        'ro': 'Geamuri termopan',
        'ru': 'Стеклопакет'
    },
    'intercom': {
        'en': 'Intercom',
        'ro': 'Interfon',
        'ru': 'Домофон'
    },
    'internet': {
        'en': 'Internet',
        'ro': 'Internet',
        'ru': 'Интернет'
    },
    'laminate_flooring': {
        'en': 'Laminate Flooring',
        'ro': 'Laminat',
        'ru': 'Ламинат'
    },
    'phone_line': {
        'en': 'Phone Line',
        'ro': 'Linie telefonică',
        'ru': 'Телефонная линия'
    },
    'parquet_flooring': {
        'en': 'Parquet Flooring',
        'ro': 'Parchet',
        'ru': 'Паркет'
    },
    'video_surveillance': {
        'en': 'Video Surveillance',
        'ro': 'Supraveghere video',
        'ru': 'Видеонаблюдение'
    },
    'playground': {
        'en': 'Playground',
        'ro': 'Teren de joacă',
        'ru': 'Детская площадка'
    },
    'armored_door': {
        'en': 'Armored Door',
        'ro': 'Ușă blindată',
        'ru': 'Бронированная дверь'
    },
    'autonomous_heating': {
        'en': 'Autonomous Heating',
        'ro': 'Încălzire autonomă',
        'ru': 'Автономное отопление'
    },
    'floor_heating': {
        'en': 'Floor Heating',
        'ro': 'Încălzire prin pardoseală',
        'ru': 'Теплые полы'
    }
}

# ============================================================================
# FEATURES - Canonical English keys with RO/RU translations
# ============================================================================
FEATURES = {
    'balcony': {
        'en': 'Balcony',
        'ro': 'Balcon/ lojie',
        'ru': 'Балкон / лоджия'
    },
    'parking': {
        'en': 'Parking Space',
        'ro': 'Loc de parcare',
        'ru': 'Парковочное место'
    },
    'layout': {
        'en': 'Layout',
        'ro': 'Compartimentare',
        'ru': 'Планировка'
    },
    'floor': {
        'en': 'Floor',
        'ro': 'Etaj',
        'ru': 'Этаж'
    },
    'housing_stock': {
        'en': 'Housing Stock',
        'ro': 'Fond locativ',
        'ru': 'Жилой фонд'
    },
    'bathroom': {
        'en': 'Bathroom',
        'ro': 'Grup sanitar',
        'ru': 'Санузел'
    },
    'number_of_rooms': {
        'en': 'Number of Rooms',
        'ro': 'Număr de camere',
        'ru': 'Количество комнат'
    },
    'number_of_floors': {
        'en': 'Number of Floors',
        'ro': 'Număr de etaje',
        'ru': 'Количество этажей'
    },
    'condition': {
        'en': 'Condition',
        'ro': 'Starea apartamentului',
        'ru': 'Состояние квартиры'
    },
    'total_area': {
        'en': 'Total Area',
        'ro': 'Suprafață totală',
        'ru': 'Общая площадь'
    },
    'building_type': {
        'en': 'Building Type',
        'ro': 'Tip clădire',
        'ru': 'Тип здания'
    },
    'listing_author': {
        'en': 'Listing Author',
        'ro': 'Autorul anunțului',
        'ru': 'Автор объявления'
    },
    'developer': {
        'en': 'Developer',
        'ro': 'Dezvoltator',
        'ru': 'Застройщик'
    },
    'living_room': {
        'en': 'Living Room',
        'ro': 'Living',
        'ru': 'Гостиная'
    }
}

# ============================================================================
# TRANSLATION FUNCTIONS
# ============================================================================

def translate_amenity(key: str, to_lang: str = 'en') -> str:
    """
    Translate amenity key to target language.
    
    Args:
        key: English amenity key (e.g., 'furnished')
        to_lang: Target language ('en', 'ro', 'ru')
    
    Returns:
        Translated amenity name
    """
    return AMENITIES.get(key, {}).get(to_lang, key)


def translate_feature(key: str, to_lang: str = 'en') -> str:
    """
    Translate feature key to target language.
    
    Args:
        key: English feature key (e.g., 'balcony')
        to_lang: Target language ('en', 'ro', 'ru')
    
    Returns:
        Translated feature name
    """
    return FEATURES.get(key, {}).get(to_lang, key)


def get_amenity_key_from_text(text: str, from_lang: str = 'ro') -> Optional[str]:
    """
    Reverse lookup: Get English key from translated text.
    
    Args:
        text: Translated amenity name (e.g., 'Mobilat', 'Меблирована')
        from_lang: Source language ('ro' or 'ru')
    
    Returns:
        English key (e.g., 'furnished') or None if not found
    
    Example:
        get_amenity_key_from_text('Mobilat', 'ro') -> 'furnished'
        get_amenity_key_from_text('Меблирована', 'ru') -> 'furnished'
    """
    for key, translations in AMENITIES.items():
        if translations.get(from_lang) == text:
            return key
    return None


def get_feature_key_from_text(text: str, from_lang: str = 'ro') -> Optional[str]:
    """
    Reverse lookup: Get English key from translated text.
    
    Args:
        text: Translated feature name
        from_lang: Source language ('ro' or 'ru')
    
    Returns:
        English key or None if not found
    """
    for key, translations in FEATURES.items():
        if translations.get(from_lang) == text:
            return key
    return None


def normalize_scraped_amenities(amenities: Dict[str, Dict], source_lang: str = 'ro') -> Dict[str, str]:
    """
    Convert scraped amenities from any language to English keys.
    
    Args:
        amenities: Bilingual amenities dict
            {
                'ro': {'Mobilat': 'Da', 'Internet': 'Da'},
                'ru': {'Меблирована': 'Да', 'Интернет': 'Да'}
            }
        source_lang: Which language to use as source ('ro' or 'ru')
    
    Returns:
        Normalized dict with English keys
            {'furnished': 'yes', 'internet': 'yes'}
    """
    normalized = {}
    
    # Use the source language (usually 'ro' from primary scrape)
    source_amenities = amenities.get(source_lang, {})
    
    for text, value in source_amenities.items():
        english_key = get_amenity_key_from_text(text, source_lang)
        if english_key:
            # Normalize value to English - handle both string and boolean
            if isinstance(value, bool):
                normalized_value = 'yes' if value else 'no'
            elif isinstance(value, str):
                normalized_value = 'yes' if value.lower() in ['da', 'да', 'yes', 'true'] else value
            else:
                normalized_value = str(value)
            normalized[english_key] = normalized_value
        else:
            # Unknown amenity - store as-is with warning
            print(f"⚠️  Unknown amenity: {text} ({source_lang})")
            # Handle boolean values for unknown amenities too
            if isinstance(value, bool):
                normalized[text.lower().replace(' ', '_')] = 'yes' if value else 'no'
            else:
                normalized[text.lower().replace(' ', '_')] = str(value)
    
    return normalized


def normalize_scraped_features(features: Dict[str, Dict], source_lang: str = 'ro') -> Dict[str, str]:
    """
    Convert scraped features from any language to English keys.
    
    Args:
        features: Bilingual features dict
            {
                'ro': {'Caracteristici': {'Balcon/ lojie': 'Da'}},
                'ru': {'Характеристики': {'Балкон / лоджия': 'Да'}}
            }
        source_lang: Which language to use as source ('ro' or 'ru')
    
    Returns:
        Normalized dict with English keys
            {'balcony': 'yes'}
    """
    normalized = {}
    
    # Get source language features
    source_features = features.get(source_lang, {})
    
    # Features might be nested in sections
    if isinstance(source_features, dict):
        for section, items in source_features.items():
            if isinstance(items, dict):
                for text, value in items.items():
                    english_key = get_feature_key_from_text(text, source_lang)
                    if english_key:
                        # Handle both string and boolean values
                        if isinstance(value, bool):
                            normalized_value = 'yes' if value else 'no'
                        elif isinstance(value, str):
                            normalized_value = 'yes' if value.lower() in ['da', 'да', 'yes', 'true'] else value
                        else:
                            normalized_value = str(value)
                        normalized[english_key] = normalized_value
                    else:
                        # Unknown feature - store as-is
                        print(f"⚠️  Unknown feature: {text} ({source_lang})")
                        if isinstance(value, bool):
                            normalized[text.lower().replace(' ', '_')] = 'yes' if value else 'no'
                        else:
                            normalized[text.lower().replace(' ', '_')] = str(value)
    
    return normalized


def get_amenities_for_display(listing_amenities: Dict[str, str], lang: str = 'ro') -> Dict[str, str]:
    """
    Convert stored English amenities to display language.
    
    Args:
        listing_amenities: Dict with English keys from database
            {'furnished': 'yes', 'internet': 'yes'}
        lang: Target display language ('ro' or 'ru')
    
    Returns:
        Dict with translated keys for display
            RO: {'Mobilat': 'Da', 'Internet': 'Da'}
            RU: {'Меблирована': 'Да', 'Интернет': 'Да'}
    """
    display = {}
    
    for key, value in listing_amenities.items():
        # Translate key
        translated_key = translate_amenity(key, lang)
        
        # Translate value
        if value.lower() == 'yes':
            translated_value = 'Da' if lang == 'ro' else 'Да'
        elif value.lower() == 'no':
            translated_value = 'Nu' if lang == 'ro' else 'Нет'
        else:
            translated_value = value
        
        display[translated_key] = translated_value
    
    return display


def get_features_for_display(listing_features: Dict[str, str], lang: str = 'ro') -> Dict[str, Dict]:
    """
    Convert stored English features to display language.
    
    Args:
        listing_features: Dict with English keys from database
            {'balcony': 'yes', 'parking': 'yes', 'living_room': 'yes'}
        lang: Target display language ('ro' or 'ru')
    
    Returns:
        Dict with translated keys wrapped in section for display
            {'Caracteristici': {'Balcon/ lojie': 'Da', 'Loc de parcare': 'Da', 'Living': 'Da'}}
    """
    section_name = 'Caracteristici' if lang == 'ro' else 'Характеристики'
    features_dict = {}
    
    for key, value in listing_features.items():
        # Try to translate key - if not found in FEATURES dict, check if it's a known feature
        if key in FEATURES:
            translated_key = FEATURES[key].get(lang, key)
        else:
            # Unknown feature - keep the English key as fallback
            # This ensures features show up even if not in translation dict
            translated_key = key.replace('_', ' ').title()
        
        # Translate value
        if isinstance(value, str) and value.lower() == 'yes':
            translated_value = 'Da' if lang == 'ro' else 'Да'
        elif isinstance(value, str) and value.lower() == 'no':
            translated_value = 'Nu' if lang == 'ro' else 'Нет'
        else:
            translated_value = str(value)
        
        features_dict[translated_key] = translated_value
    
    # Wrap in section
    return {section_name: features_dict} if features_dict else {}


def get_all_amenity_keys() -> list:
    """Get list of all English amenity keys."""
    return list(AMENITIES.keys())


def get_all_feature_keys() -> list:
    """Get list of all English feature keys."""
    return list(FEATURES.keys())
