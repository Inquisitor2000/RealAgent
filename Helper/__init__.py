"""
Helper package for RealAgent
Contains utility modules for address parsing, geocoding, translations, and database management.
"""

from .geoguess import (
    detect_cyrillic_text,
    translate_russian_to_romanian,
    parse_address_string,
    build_geocode_queries,
    get_all_translations
)

from .translations import (
    PROPERTY_FEATURE_TRANSLATIONS,
    ROMANIAN_TO_RUSSIAN_FEATURES,
    get_property_feature_translations,
    get_romanian_to_russian_translations
)

from .database import (
    init_mainframe_db,
    save_listing_to_mainframe,
    get_listing_from_mainframe,
    get_all_listings,
    update_listing_status,
    delete_listing_from_mainframe,
    MAINFRAME_DB_PATH
)

# New universal builder system
from .builder import (
    build_listing_html,
    rebuild_listing,
    batch_rebuild,
    get_available_templates,
    get_template_info,
    validate_template
)

# Interactive map overlay for address correction
try:
    from .map_overlay import (
        create_interactive_map,
        MapOverlayServer
    )
    MAP_OVERLAY_AVAILABLE = True
except ImportError:
    # Folium not installed, map overlay not available
    MAP_OVERLAY_AVAILABLE = False
    create_interactive_map = None
    MapOverlayServer = None


__all__ = [
    # Geoguess functions
    'detect_cyrillic_text',
    'translate_russian_to_romanian',
    'parse_address_string',
    'build_geocode_queries',
    'get_all_translations',
    # Translation constants and functions
    'PROPERTY_FEATURE_TRANSLATIONS',
    'ROMANIAN_TO_RUSSIAN_FEATURES',
    'get_property_feature_translations',
    'get_romanian_to_russian_translations',
    # Database functions
    'init_mainframe_db',
    'save_listing_to_mainframe',
    'get_listing_from_mainframe',
    'get_all_listings',
    'update_listing_status',
    'delete_listing_from_mainframe',
    'MAINFRAME_DB_PATH',
    # New universal builder functions
    'build_listing_html',
    'rebuild_listing',
    'batch_rebuild',
    'get_available_templates',
    'get_template_info',
    'validate_template',
    # Interactive map overlay functions
    'create_interactive_map',
    'MapOverlayServer',
    'MAP_OVERLAY_AVAILABLE',
]
