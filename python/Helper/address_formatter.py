"""
Address Formatter and Translator for RealAgent
===============================================

This module formats and translates addresses from OpenStreetMap format
to user-friendly Romanian and Russian display formats.

Usage:
    from Helper.address_formatter import format_address_for_display
    
    formatted = format_address_for_display(
        "58, Poștei Street, Visterniceni, Rîșcani Sector, Chișinău, Moldova"
    )
    # Returns: {
    #     'ro': 'Chișinău, Strada Poștei 58',
    #     'ru': 'Кишинёв, Улица Поштей 58'
    # }
"""

import re
from typing import Dict, Optional

# Romanian to Russian city translations
CITY_TRANSLATIONS = {
    'chișinău': 'Кишинёв',
    'chisinau': 'Кишинёв',
    'bălți': 'Бельцы',
    'balti': 'Бельцы',
    'tiraspol': 'Тирасполь',
    'bender': 'Бендеры',
    'cahul': 'Кагул',
    'soroca': 'Сорока',
    'orhei': 'Орхей',
    'ungheni': 'Унгены',
    'comrat': 'Комрат',
    'ceadîr-lunga': 'Чадыр-Лунга',
    'strășeni': 'Стрэшены',
    'căușeni': 'Каушены',
    'hîncești': 'Хынчешты',
    'edineț': 'Единцы',
    'drochia': 'Дрокия',
    'florești': 'Флорешты',
    'rezina': 'Резина',
    'rîbnița': 'Рыбница',
    'dubăsari': 'Дубоссары'
}

# Street type translations
STREET_TYPE_TRANSLATIONS = {
    'ro_to_ru': {
        'strada': 'Улица',
        'str.': 'Ул.',
        'str': 'Ул.',
        'bulevardul': 'Бульвар',
        'bd.': 'Бул.',
        'bd': 'Бул.',
        'piața': 'Площадь',
        'aleea': 'Переулок',
        'calea': 'Шоссе',
        'șoseaua': 'Шоссе',
        'intrarea': 'Проезд',
        'pasajul': 'Проход'
    },
    'en_to_ro': {
        'street': 'Strada',
        'boulevard': 'Bulevardul',
        'avenue': 'Bulevardul',
        'square': 'Piața',
        'lane': 'Aleea',
        'road': 'Calea',
        'way': 'Calea'
    },
    'en_to_ru': {
        'street': 'Улица',
        'boulevard': 'Бульвар',
        'avenue': 'Бульвар',
        'square': 'Площадь',
        'lane': 'Переулок',
        'road': 'Шоссе',
        'way': 'Шоссе'
    }
}

# Romanian street name translations to Russian (common streets)
STREET_NAME_TRANSLATIONS = {
    'ștefan cel mare': 'Стефан чел Маре',
    'stefan cel mare': 'Стефан чел Маре',
    'mihai eminescu': 'Михай Эминеску',
    'alexandru cel bun': 'Александру чел Бун',
    'puskin': 'Пушкин',
    'pușkin': 'Пушкин',
    'moscow': 'Москва',
    'moscova': 'Москва',
    'bucuresti': 'Бухарест',
    'bucurești': 'Бухарест',
    'bucharest': 'Бухарест',
    'independenței': 'Независимости',
    'independentei': 'Независимости',
    'miorița': 'Миорица',
    'miorita': 'Миорица',
    'dacia': 'Дачия',
    'alba iulia': 'Алба-Юлия',
    'vasile alecsandri': 'Василе Александри',
    'ion creangă': 'Ион Крянгэ',
    'ion creanga': 'Ион Крянгэ',
    'mihail kogălniceanu': 'Михаил Когэлничану',
    'mihail kogalniceanu': 'Михаил Kogэлничану',
    'maria cibotari': 'Мария Чиботарь',
    'grenoble': 'Гренобль',
    'paris': 'Париж',
    'roma': 'Рим',
    'rome': 'Рим',
    'tighina': 'Тигина',
    'ismail': 'Измаил',
    'prut': 'Прут',
    'nistru': 'Днестр',
    'dniester': 'Днестр'
}

def normalize_text(text: str) -> str:
    """Normalize text by removing diacritics and converting to lowercase."""
    if not text:
        return ""
    
    diacritics_map = {
        'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
        'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T'
    }
    
    normalized = text.lower()
    for diacritic, replacement in diacritics_map.items():
        normalized = normalized.replace(diacritic.lower(), replacement)
    
    return normalized.strip()

def extract_address_components(address: str) -> Dict[str, str]:
    """
    Extract components from a full address string.
    
    Args:
        address: Full address string from geocoding
        
    Returns:
        Dictionary with extracted components
    """
    if not address:
        return {}
    
    # Split by commas and clean each part
    parts = [part.strip() for part in address.split(',')]
    
    components = {
        'house_number': '',
        'street_name': '',
        'street_type': '',
        'district': '',
        'city': '',
        'country': ''
    }
    
    # Find house number (usually first part or embedded in street)
    # Updated pattern to handle: 19, 19A, 19/8, 19-B, 19/8A, etc.
    house_number_pattern = r'\b(\d+[\w/-]*)\b'
    
    for i, part in enumerate(parts):
        part_lower = part.lower()
        
        # Skip empty parts
        if not part.strip():
            continue
            
        # Check for country (usually last)
        if i == len(parts) - 1 or 'moldova' in part_lower or 'md-' in part_lower:
            components['country'] = part
            continue
            
        # Check for city (common Moldovan cities)
        city_found = False
        for city_key, city_ru in CITY_TRANSLATIONS.items():
            if city_key in normalize_text(part):
                components['city'] = part
                city_found = True
                break
        
        if city_found:
            continue
            
        # Check for district/sector
        if 'sector' in part_lower or 'district' in part_lower or 'raion' in part_lower:
            components['district'] = part
            continue
            
        # Check for street (first part usually contains street info)
        if i == 0 or any(st_type in part_lower for st_type in ['street', 'strada', 'str', 'boulevard', 'bulevardul', 'bd', 'piața', 'aleea']):
            # Extract house number
            house_match = re.search(house_number_pattern, part)
            if house_match:
                components['house_number'] = house_match.group(1)
                # Remove house number from street part
                street_part = re.sub(house_number_pattern, '', part).strip()
            else:
                street_part = part.strip()
            
            # Extract street type and name
            street_part = street_part.rstrip(',').strip()
            
            # Check for street type
            for st_type in ['street', 'strada', 'str.', 'str', 'boulevard', 'bulevardul', 'bd.', 'bd', 'piața', 'aleea', 'calea']:
                if street_part.lower().startswith(st_type.lower()):
                    components['street_type'] = st_type
                    components['street_name'] = street_part[len(st_type):].strip()
                    break
                elif street_part.lower().endswith(' ' + st_type.lower()):
                    components['street_type'] = st_type
                    components['street_name'] = street_part[:-len(st_type)-1].strip()
                    break
            
            # If no street type found, treat whole part as street name
            if not components['street_type'] and not components['street_name']:
                components['street_name'] = street_part
            
            continue
    
    return components

def translate_street_name(street_name: str) -> str:
    """Translate Romanian street name to Russian."""
    if not street_name:
        return street_name
    
    normalized_name = normalize_text(street_name)
    
    # Check for direct translations
    for ro_name, ru_name in STREET_NAME_TRANSLATIONS.items():
        if normalize_text(ro_name) == normalized_name:
            return ru_name
    
    # If no direct translation, return original with proper case
    return street_name.title()

def format_address_for_display(address: str) -> Dict[str, str]:
    """
    Format address for display in Romanian and Russian.
    
    Args:
        address: Full address string from geocoding
        
    Returns:
        Dictionary with 'ro' and 'ru' formatted addresses
    """
    if not address:
        return {'ro': '', 'ru': ''}
    
    components = extract_address_components(address)
    
    # Default fallback
    if not components.get('city') and not components.get('street_name'):
        return {'ro': address, 'ru': address}
    
    # Format Romanian address
    ro_parts = []
    
    # Add city first
    if components.get('city'):
        city = components['city']
        # Clean up city name
        city = re.sub(r'\s+(municipality|municipiu)', '', city, flags=re.IGNORECASE).strip()
        ro_parts.append(city)
    
    # Add street information
    street_parts = []
    
    # Determine street type in Romanian
    street_type_ro = 'Strada'  # Default
    if components.get('street_type'):
        st_type = components['street_type'].lower()
        if st_type in ['boulevard', 'bulevardul', 'bd', 'bd.']:
            street_type_ro = 'Bulevardul'
        elif st_type in ['piața', 'square']:
            street_type_ro = 'Piața'
        elif st_type in ['aleea', 'lane']:
            street_type_ro = 'Aleea'
        elif st_type in ['calea', 'road', 'way']:
            street_type_ro = 'Calea'
        elif st_type in STREET_TYPE_TRANSLATIONS['en_to_ro']:
            street_type_ro = STREET_TYPE_TRANSLATIONS['en_to_ro'][st_type]
    
    if components.get('street_name'):
        street_parts.append(street_type_ro)
        street_parts.append(components['street_name'])
        
        if components.get('house_number'):
            street_parts.append(components['house_number'])
    
    if street_parts:
        ro_parts.append(' '.join(street_parts))
    
    ro_address = ', '.join(ro_parts)
    
    # Format Russian address
    ru_parts = []
    
    # Add city in Russian
    if components.get('city'):
        city = components['city']
        city_normalized = normalize_text(city)
        
        # Find Russian translation
        ru_city = None
        for ro_city, ru_translation in CITY_TRANSLATIONS.items():
            if ro_city in city_normalized:
                ru_city = ru_translation
                break
        
        if not ru_city:
            # Fallback: use original city name
            ru_city = re.sub(r'\s+(municipality|municipiu)', '', city, flags=re.IGNORECASE).strip()
        
        ru_parts.append(ru_city)
    
    # Add street information in Russian
    street_parts_ru = []
    
    # Determine street type in Russian
    street_type_ru = 'Улица'  # Default
    if components.get('street_type'):
        st_type = components['street_type'].lower()
        if st_type in STREET_TYPE_TRANSLATIONS['ro_to_ru']:
            street_type_ru = STREET_TYPE_TRANSLATIONS['ro_to_ru'][st_type]
        elif st_type in STREET_TYPE_TRANSLATIONS['en_to_ru']:
            street_type_ru = STREET_TYPE_TRANSLATIONS['en_to_ru'][st_type]
    
    if components.get('street_name'):
        street_parts_ru.append(street_type_ru)
        
        # Translate street name
        ru_street_name = translate_street_name(components['street_name'])
        street_parts_ru.append(ru_street_name)
        
        if components.get('house_number'):
            street_parts_ru.append(components['house_number'])
    
    if street_parts_ru:
        ru_parts.append(' '.join(street_parts_ru))
    
    ru_address = ', '.join(ru_parts)
    
    return {
        'ro': ro_address,
        'ru': ru_address
    }

def test_address_formatter():
    """Test the address formatter with sample addresses."""
    test_addresses = [
        "58, Poștei Street, Visterniceni, Rîșcani Sector, Chișinău, Chișinău Municipality, MD-2059, Moldova",
        "Strada Ștefan cel Mare 123, Centru, Chișinău, Moldova",
        "Bulevardul Moscova 45, Botanica, Chișinău, Moldova",
        "Piața Centrală 1, Chișinău, Moldova",
        "25, Puskin Street, Chișinău, Moldova"
    ]
    
    print("🧪 Testing Address Formatter")
    print("=" * 60)
    
    for address in test_addresses:
        print(f"\n📍 Original: {address}")
        formatted = format_address_for_display(address)
        print(f"🇷🇴 Romanian: {formatted['ro']}")
        print(f"🇷🇺 Russian: {formatted['ru']}")
        print("-" * 40)

if __name__ == "__main__":
    test_address_formatter()
