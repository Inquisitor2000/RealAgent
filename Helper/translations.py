# -*- coding: utf-8 -*-
"""
Russian-to-Romanian Translation Mappings for Property Features

This module provides translation dictionaries for converting
Russian property features to their Romanian equivalents.
Used for bilingual property listings (Romanian/Russian).

Features:
- Property feature translations (24 standard features)
- Building amenities and characteristics
- Interior and exterior features

Author: RealAgent Property System
Version: 3.0
"""

# ============================================================================
# PROPERTY FEATURE TRANSLATIONS
# ============================================================================
PROPERTY_FEATURE_TRANSLATIONS = {
    # ========================================================================
    # Building Features
    # ========================================================================
    'Готова к въезду': 'Gata de mutat',
    'Готова для проживания': 'Gata pentru mutare',
    'Пристройка': 'Anexă',
    'Терраса': 'Terasă',
    'Отдельный вход': 'Intrare separată',
    'Парковая зона': 'Zonă cu parc',
    'Зеленая зона': 'Zonă verde',
    
    # ========================================================================
    # Interior Features
    # ========================================================================
    'Меблирована': 'Mobilată',
    'С мебелью': 'Cu mobilă',
    'Мебель включена': 'Mobilier inclus',
    'С бытовой техникой': 'Cu tehnică electrocasnică',
    'С техникой': 'Cu aparate',
    'Техника включена': 'Tehnică inclusă',
    'Бытовая техника': 'Electrocasnice',
    
    # ========================================================================
    # Heating & Climate
    # ========================================================================
    'Автономное отопление': 'Încălzire autonomă',
    'Независимое отопление': 'Încălzire independentă',
    'Кондиционер': 'Aer condiționat',
    'Кондиционирование': 'Climatizare',
    'Климат-контроль': 'Control climatic',
    'Теплые полы': 'Încălzire în pardoseală',
    'Подогрев пола': 'Pardoseală caldă',
    'Напольное отопление': 'Încălzire prin pardoseală',
    
    # ========================================================================
    # Windows & Doors
    # ========================================================================
    'Стеклопакет': 'Termopan',
    'Стеклопакеты': 'Geamuri termopan',
    'Пластиковые окна': 'Ferestre termopan',
    'Панорамные окна': 'Geamuri panoramice',
    'Большие окна': 'Ferestre panoramice',
    'Бронированная дверь': 'Ușă blindată',
    'Металлическая дверь': 'Ușă metalică',
    'Дверь безопасности': 'Ușă de securitate',
    
    # ========================================================================
    # Flooring
    # ========================================================================
    'Паркет': 'Parchet',
    'Ламинат': 'Laminat',
    
    # ========================================================================
    # Communication & Security
    # ========================================================================
    'Телефонная линия': 'Linie telefonică',
    'Стационарный телефон': 'Telefon fix',
    'Система умный дом': 'Sistem casă inteligentă',
    'Умный дом': 'Smart home',
    'Автоматизация': 'Automatizare',
    'Домофон': 'Interfon',
    'Интернет': 'Internet',
    'Интернет-соединение': 'Conexiune internet',
    'ТВ кабель': 'Cablu TV',
    'Кабельное ТВ': 'Televiziune prin cablu',
    'Телевидение': 'TV prin cablu',
    'Сигнализация': 'Sistem de alarmă',
    'Система безопасности': 'Alarmă',
    'Видеонаблюдение': 'Supraveghere video',
    'Камеры наблюдения': 'Camere de supraveghere',
    
    # ========================================================================
    # Building Amenities
    # ========================================================================
    'Лифт': 'Ascensor',
    'Детская площадка': 'Teren de joacă',
    'Игровая площадка': 'Loc de joacă pentru copii',
    
    # ========================================================================
    # Property Characteristic Field Names (from 999.md Caracteristici section)
    # ========================================================================
    'Автор объявления': 'Autorul anunțului',
    'Количество комнат': 'Număr de camere',
    'Общая площадь': 'Suprafață totală',
    'Жилая площадь': 'Suprafață locuibilă',
    'Площадь кухни': 'Suprafață bucătărie',
    'Жилой фонд': 'Fond locativ',
    'Этаж': 'Etaj',
    'Количество этажей': 'Număr de etaje',
    'Застройщик': 'Dezvoltator',
    'Тип здания': 'Tip clădire',
    'Состояние квартиры': 'Starea apartamentului',
    'Планировка': 'Compartimentare',
    'Тип планировки': 'Tipul de plan',
    'Количество санузлов': 'Număr de băi',
    'Количество балконов': 'Număr de balcoane',
    'Высота потолка': 'Înălțimea tavanului',
    'Тип парковки': 'Tipul de parcare',
    'Парковка': 'Parcare',
    'Гостиная': 'Living',  # Living room
    'Санузел': 'Grup sanitar',  # Bathroom/toilet group
    'Балкон': 'Balcon/ lojie',  # Balcony/loggia
    'Высота потолков': 'Înălțimea tavanelor',  # Ceiling height (plural)
    'Парковочное место': 'Loc de parcare',  # Parking space
    
    # ========================================================================
    # Property Characteristic Values
    # ========================================================================
    'Агентство': 'Agenție',
    'Собственник': 'Proprietar',
    'Новостройка': 'Construcție nouă',
    'Вторичный': 'Secundar',
    'Евроремонт': 'Reparație euro',
    'Требует ремонт': 'Necesită reparație',
    'Белая': 'Alb',
    'Белый вариант': 'Varianta albă',
    'Старый тип': 'De tip vechi',
    'Улучшенная': 'Îmbunătățită',
    'Свободная': 'Liberă',
    'Гараж': 'Garaj',
    'Подземная': 'Subteran',
    'Подземная парковка': 'Subterană',  # Underground parking
    'Уличная': 'Stradă',
    'Застройщик недвижимости': 'Dezvoltator imobiliar',  # Real estate developer
    'Квартира с 2 комнатами': 'Apartament cu 2 camere',  # 2-room apartment
    'Квартира с гостиной': 'Apartament cu living',  # Apartment with living room
    'Новостройки': 'Construcții noi',  # New constructions
    'Индивидуальная': 'Individuală',  # Individual layout
    'Белый вариант': 'Variantă albă',  # White variant/shell
    'Открытая': 'Deschis',  # Open (parking)
    'Нет': 'Nu',  # No
    'Да': 'Da',  # Yes
    
    # ========================================================================
    # Feature Section Headers
    # ========================================================================
    'Характеристики': 'Caracteristici',
    'Особенности': 'Particularități',
    'Удобства': 'Facilități',
    'Коммуникации': 'Comunicații',
    'Безопасность': 'Securitate',
    'Отопление': 'Încălzire',
    'Состояние': 'Stare',
}

# ============================================================================
# STREET NAME TRANSLATIONS (Russian to Romanian/Latin)
# ============================================================================
# For better OpenStreetMap geocoding, convert Russian street names to their 
# Romanian/Latin equivalents commonly used in Moldova's mapping data

STREET_NAME_TRANSLATIONS = {
    # Common Chișinău streets
    'Николай Зелински': 'Nicolae Zelinski',
    'Зелински': 'Zelinski',
    'Иона Крянгэ': 'Iona Creangă',
    'Крянгэ': 'Creangă',
    'Михаил Когэлничану': 'Mihail Kogălniceanu',
    'Когэлничану': 'Kogălniceanu',
    'Андрей Лупан': 'Andrei Lupan',
    'Лупан': 'Lupan',
    'Александр Пушкин': 'Alexandr Pușkin',
    'Пушкин': 'Pușkin',
    'Ион Лука Караджале': 'Ion Luca Caragiale',
    'Караджале': 'Caragiale',
    'Константин Брынкуш': 'Constantin Brâncuși',
    'Брынкуш': 'Brâncuși',
    'Штефан Великий': 'Ștefan cel Mare',
    'Великий': 'cel Mare',
    'Василий Алехандри': 'Vasile Alecsandri',
    'Алехандри': 'Alecsandri',
    'Михаил Еминеску': 'Mihai Eminescu',
    'Еминеску': 'Eminescu',
    'Григорий Виеру': 'Grigore Vieru',
    'Виеру': 'Vieru',
    
    # Common prefixes
    'ул. ': 'strada ',
    'улица ': 'strada ',
    'бул. ': 'bulevardul ',
    'бульвар ': 'bulevardul ',
    'пр. ': 'prospektul ',
    'проспект ': 'prospektul ',
    'пл. ': 'piața ',
    'площадь ': 'piața ',
}

# Create reverse mapping (Romanian to Russian) for features
ROMANIAN_TO_RUSSIAN_FEATURES = {v: k for k, v in PROPERTY_FEATURE_TRANSLATIONS.items()}

# ============================================================================
# ACCESS FUNCTIONS (for backward compatibility)
# ============================================================================

def get_all_translations():
    """Return property feature translations (for backward compatibility)."""
    return PROPERTY_FEATURE_TRANSLATIONS

def get_property_feature_translations():
    """Return property feature translations."""
    return PROPERTY_FEATURE_TRANSLATIONS

def get_romanian_to_russian_translations():
    """Get Romanian to Russian feature translations."""
    return ROMANIAN_TO_RUSSIAN_FEATURES
    
def get_street_name_translations():
    """Get Russian to Romanian street name translations."""
    return STREET_NAME_TRANSLATIONS

def translate_street_name(russian_street):
    """Translate a Russian street name to Romanian/Latin equivalent.
    
    Args:
        russian_street: Russian street name string
        
    Returns:
        Translated street name or original if no translation found
    """
    if not russian_street:
        return russian_street
        
    # Try exact matches first
    if russian_street in STREET_NAME_TRANSLATIONS:
        return STREET_NAME_TRANSLATIONS[russian_street]
    
    # Try to replace prefixes
    result = russian_street
    for russian_prefix, romanian_prefix in STREET_NAME_TRANSLATIONS.items():
        if russian_prefix.endswith(' '):  # Only replace prefixes
            result = result.replace(russian_prefix, romanian_prefix)
    
    return result
