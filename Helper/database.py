"""
Mainframe Database Module
Centralized database management for all listings.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any


# Default Mainframe.db location
MAINFRAME_DB_PATH = Path(__file__).parent.parent / "Mainframe.db"


def init_mainframe_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Initialize Mainframe.db with schema.
    
    Args:
        db_path: Optional custom path for database. Defaults to project root.
        
    Returns:
        SQLite connection object
    """
    if db_path is None:
        db_path = MAINFRAME_DB_PATH
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Enable WAL mode for better concurrent access
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=NORMAL')
    c.execute('PRAGMA temp_store=MEMORY')
    c.execute('PRAGMA foreign_keys=ON')
    
    # Main listings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            url TEXT UNIQUE,
            domain TEXT,
            title_ro TEXT,
            title_ru TEXT,
            description_ro TEXT,
            description_ru TEXT,
            price_json TEXT,
            address TEXT,
            display_address TEXT,
            geocoding_address TEXT,
            contact TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            folder_path TEXT,
            template_name TEXT DEFAULT 'luna',
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'deleted')),
            user_corrected_address INTEGER DEFAULT 0
        )
    ''')
    
    # Migration: Add template_name column if it doesn't exist (for existing databases)
    try:
        c.execute('SELECT template_name FROM listings LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE listings ADD COLUMN template_name TEXT DEFAULT "luna"')
        conn.commit()
    
    # Migration: Add user_corrected_address column if it doesn't exist
    try:
        c.execute('SELECT user_corrected_address FROM listings LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE listings ADD COLUMN user_corrected_address INTEGER DEFAULT 0')
        conn.commit()
    
    # Migration: Add sold column if it doesn't exist
    try:
        c.execute('SELECT sold FROM listings LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE listings ADD COLUMN sold TEXT DEFAULT "no" CHECK(sold IN ("yes", "no"))')
        conn.commit()
    
    # Migration: Add rented column if it doesn't exist
    try:
        c.execute('SELECT rented FROM listings LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE listings ADD COLUMN rented TEXT DEFAULT "no" CHECK(rented IN ("yes", "no"))')
        conn.commit()
    
    # Migration: Add listing_type column if it doesn't exist (for_rent, for_sale, both)
    try:
        c.execute('SELECT listing_type FROM listings LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE listings ADD COLUMN listing_type TEXT DEFAULT "for_sale" CHECK(listing_type IN ("for_rent", "for_sale", "both"))')
        conn.commit()
    
    # Migration: Add property_type column if it doesn't exist (apartment, house, commercial)
    try:
        c.execute('SELECT property_type FROM listings LIMIT 1')
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        c.execute('ALTER TABLE listings ADD COLUMN property_type TEXT DEFAULT "apartment" CHECK(property_type IN ("apartment", "house", "commercial", "other"))')
        conn.commit()
    
    # Images table
    c.execute('''
        CREATE TABLE IF NOT EXISTS listing_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            image_url TEXT,
            local_path TEXT,
            position INTEGER NOT NULL,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
            UNIQUE(listing_id, position)
        )
    ''')
    
    # Features table (normalized, supports multilingual)
    c.execute('''
        CREATE TABLE IF NOT EXISTS listing_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            lang TEXT NOT NULL CHECK(lang IN ('en', 'ro', 'ru')),
            section TEXT,
            feature_key TEXT,
            feature_value TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
        )
    ''')
    
    # NOTE: standard_features table removed - use listing_features and listing_amenities instead
    
    # Map data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS listing_map (
            listing_id TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            map_title TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
        )
    ''')
    
    # Amenities table (separate from characteristics)
    c.execute('''
        CREATE TABLE IF NOT EXISTS listing_amenities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            lang TEXT NOT NULL CHECK(lang IN ('en', 'ro', 'ru')),
            amenity_key TEXT,
            amenity_value TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
        )
    ''')
    
    # POI (Points of Interest) data table - pre-generated during listing creation
    c.execute('''
        CREATE TABLE IF NOT EXISTS listing_pois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            category TEXT NOT NULL,
            poi_data TEXT NOT NULL,  -- JSON data for all POIs in this category
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            radius INTEGER DEFAULT 500,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
            UNIQUE(listing_id, category)
        )
    ''')
    
    # Journal entries table - for logs and comments
    c.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT,
            entry_type TEXT CHECK(entry_type IN ('log', 'comment', 'note')) DEFAULT 'log',
            title TEXT,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            user TEXT,
            tags TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
        )
    ''')
    
    # Create indices for better performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_listings_created ON listings(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_images_listing ON listing_images(listing_id, position)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_features_listing ON listing_features(listing_id, lang)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_amenities_listing ON listing_amenities(listing_id, lang)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pois_listing ON listing_pois(listing_id, category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_journal_listing ON journal_entries(listing_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at DESC)')
    
    conn.commit()
    return conn


def save_listing_to_mainframe(listing_data: Dict[str, Any], db_path: Optional[Path] = None) -> bool:
    """
    Save or update a listing in Mainframe.db.
    
    Args:
        listing_data: Dictionary containing all listing information
        db_path: Optional custom database path
        
    Returns:
        True if successful, False otherwise
        
    Expected listing_data structure:
    {
        'id': '102312333',
        'url': 'https://999.md/ro/102312333',
        'domain': '999.md',
        'title': 'Main title (language depends on URL)',
        'description': 'Main description',
        'price': {'EUR': '50,000 €', 'USD': '52,000 $'},
        'address': 'Full address string',
        'display_address': 'Display address',
        'geocoding_address': 'Geocoding address',
        'contact': '+373 ...',
        'images': ['url1', 'url2', ...],
        'local_images': ['images/0.jpg', 'images/1.jpg', ...],
        'features': {'ro': {section: {key: value}}, 'ru': {section: {key: value}}},
        'amenities': {'ro': {key: value}, 'ru': {key: value}},
        'map_data': {'lat': 47.0, 'lng': 28.8, 'title': '...'},
        'localized': {
            'ro': {'title': '...', 'description': '...'},
            'ru': {'title': '...', 'description': '...'}
        },
        'folder_path': 'Listings/102312333'
    }
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        listing_id = listing_data['id']
        
        # Sanitize all string fields to prevent tuple binding errors
        def ensure_string(value):
            """Convert any value to string, handling tuples/lists."""
            if isinstance(value, (tuple, list)):
                # If it's a tuple of numbers (coordinates), skip it - it's invalid
                if value and isinstance(value[0], (int, float)):
                    return ''
                # Otherwise take first element
                return str(value[0]) if value else ''
            return str(value) if value else ''
        
        # Sanitize address fields
        if 'address' in listing_data:
            listing_data['address'] = ensure_string(listing_data['address'])
        if 'display_address' in listing_data:
            listing_data['display_address'] = ensure_string(listing_data['display_address'])
        if 'geocoding_address' in listing_data:
            listing_data['geocoding_address'] = ensure_string(listing_data['geocoding_address'])
        
        # Sanitize map_data title
        if 'map_data' in listing_data and isinstance(listing_data['map_data'], dict):
            if 'title' in listing_data['map_data']:
                listing_data['map_data']['title'] = ensure_string(listing_data['map_data']['title'])
        
        # Determine language versions
        localized = listing_data.get('localized', {})
        title_ro = localized.get('ro', {}).get('title') or listing_data.get('title', '')
        title_ru = localized.get('ru', {}).get('title') or listing_data.get('title', '')
        description_ro = localized.get('ro', {}).get('description') or listing_data.get('description', '')
        description_ru = localized.get('ru', {}).get('description') or listing_data.get('description', '')
        
        # Prepare price data (ensure it's a dict, not tuple)
        price_data = listing_data.get('price', {})
        if isinstance(price_data, (tuple, list)):
            # Convert tuple/list to dict if needed
            price_data = {}
        price_json = json.dumps(price_data) if isinstance(price_data, dict) else '{}'
        
        # Insert or update main listing
        # First check if a listing with this URL already exists (different ID)
        url = listing_data.get('url', '')
        if url:
            c.execute('SELECT id FROM listings WHERE url = ? AND id != ?', (url, listing_id))
            existing = c.fetchone()
            if existing:
                # URL already exists with different ID - update that listing instead
                print(f"⚠️ URL already exists for listing {existing[0]}, updating existing record")
                listing_id = existing[0]
        
        c.execute('''
            INSERT OR REPLACE INTO listings (
                id, url, domain, title_ro, title_ru, description_ro, description_ru,
                price_json, address, display_address, geocoding_address, contact,
                created_at, updated_at, folder_path, template_name, status, user_corrected_address,
                listing_type, property_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing_id,
            listing_data.get('url', ''),
            listing_data.get('domain', ''),
            title_ro,
            title_ru,
            description_ro,
            description_ru,
            price_json,
            listing_data.get('address', ''),
            listing_data.get('display_address', ''),
            listing_data.get('geocoding_address', ''),
            listing_data.get('contact', ''),
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            listing_data.get('folder_path', ''),
            listing_data.get('template_name', 'luna'),  # Default to 'luna'
            listing_data.get('status', 'active'),
            1 if listing_data.get('user_corrected_address', False) else 0,
            listing_data.get('listing_type', 'for_sale'),  # Default to 'for_sale'
            listing_data.get('property_type', 'apartment')  # Default to 'apartment'
        ))
        
        # Delete existing related data (for clean update)
        c.execute('DELETE FROM listing_images WHERE listing_id = ?', (listing_id,))
        c.execute('DELETE FROM listing_features WHERE listing_id = ?', (listing_id,))
        c.execute('DELETE FROM listing_amenities WHERE listing_id = ?', (listing_id,))
        c.execute('DELETE FROM listing_map WHERE listing_id = ?', (listing_id,))
        
        # Insert images
        images = listing_data.get('images', [])
        local_images = listing_data.get('local_images', [])
        for i, img_url in enumerate(images):
            local_path = local_images[i] if i < len(local_images) else None
            c.execute('''
                INSERT INTO listing_images (listing_id, image_url, local_path, position)
                VALUES (?, ?, ?, ?)
            ''', (listing_id, img_url, local_path, i))
        
        # Insert features - Store BOTH original scraped values AND English normalized
        features = listing_data.get('features', {})
        if features:
            # Store original scraped values for both languages
            for lang in ['ro', 'ru']:
                lang_features = features.get(lang, {})
                if isinstance(lang_features, dict):
                    for section, items in lang_features.items():
                        if isinstance(items, dict):
                            for key, value in items.items():
                                c.execute('''
                                    INSERT INTO listing_features (listing_id, lang, section, feature_key, feature_value)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (listing_id, lang, section, key, str(value)))
        
        # Insert amenities - Store BOTH original scraped values AND English normalized
        amenities = listing_data.get('amenities', {})
        if amenities:
            # Store original scraped values for both languages
            for lang in ['ro', 'ru']:
                lang_amenities = amenities.get(lang, {})
                if isinstance(lang_amenities, dict):
                    for key, value in lang_amenities.items():
                        c.execute('''
                            INSERT INTO listing_amenities (listing_id, lang, amenity_key, amenity_value)
                            VALUES (?, ?, ?, ?)
                        ''', (listing_id, lang, key, str(value)))
        
        # NOTE: standard_features removed - data should be in amenities or features tables
        
        # Insert map data
        map_data = listing_data.get('map_data', {})
        if map_data and map_data.get('lat') and map_data.get('lng'):
            c.execute('''
                INSERT INTO listing_map (listing_id, latitude, longitude, map_title)
                VALUES (?, ?, ?, ?)
            ''', (
                listing_id,
                map_data.get('lat'),
                map_data.get('lng'),
                map_data.get('title', '')
            ))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error saving listing to Mainframe.db: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_listing_amenities_features(listing_id: str, display_lang: str = 'ro', db_path: Optional[Path] = None) -> Dict[str, Dict]:
    """
    Get amenities and features for a listing in the specified display language.
    
    Args:
        listing_id: Listing ID
        display_lang: Language for display ('ro' or 'ru')
        db_path: Optional custom database path
    
    Returns:
        Dict with 'amenities' and 'features' translated to display language
    """
    from Helper.amenity_translations import get_amenities_for_display, get_features_for_display
    
    conn = init_mainframe_db(db_path)
    c = conn.cursor()
    
    # Get amenities (stored in English)
    c.execute('SELECT amenity_key, amenity_value FROM listing_amenities WHERE listing_id = ? AND lang = ?', 
              (listing_id, 'en'))
    english_amenities = {row[0]: row[1] for row in c.fetchall()}
    
    # Get features (stored in English)
    c.execute('SELECT feature_key, feature_value FROM listing_features WHERE listing_id = ? AND lang = ?', 
              (listing_id, 'en'))
    english_features = {row[0]: row[1] for row in c.fetchall()}
    
    conn.close()
    
    # Translate to display language
    return {
        'amenities': get_amenities_for_display(english_amenities, display_lang),
        'features': get_features_for_display(english_features, display_lang)
    }


def get_listing_from_mainframe(listing_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve a complete listing from Mainframe.db.
    
    Args:
        listing_id: Listing ID to retrieve
        db_path: Optional custom database path
        
    Returns:
        Dictionary with all listing data, or None if not found
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        # Get main listing data
        c.execute('SELECT * FROM listings WHERE id = ?', (listing_id,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return None
        
        listing = dict(row)
        listing['price'] = json.loads(listing['price_json']) if listing.get('price_json') else {}
        
        # Get images
        c.execute('''
            SELECT image_url, local_path, position 
            FROM listing_images 
            WHERE listing_id = ? 
            ORDER BY position
        ''', (listing_id,))
        images = []
        local_images = []
        for img_row in c.fetchall():
            images.append(img_row[0])
            if img_row[1]:
                local_images.append(img_row[1])
        listing['images'] = images
        listing['local_images'] = local_images
        
        # Get features (use original scraped values for each language)
        listing['features'] = {'ro': {}, 'ru': {}}
        c.execute('''
            SELECT lang, section, feature_key, feature_value 
            FROM listing_features 
            WHERE listing_id = ?
        ''', (listing_id,))
        for feat_row in c.fetchall():
            lang, section, key, value = feat_row
            if lang in ['ro', 'ru']:
                if section not in listing['features'][lang]:
                    listing['features'][lang][section] = {}
                listing['features'][lang][section][key] = value
        
        # Get amenities (use original scraped values for each language)
        listing['amenities'] = {'ro': {}, 'ru': {}}
        c.execute('''
            SELECT lang, amenity_key, amenity_value 
            FROM listing_amenities 
            WHERE listing_id = ?
        ''', (listing_id,))
        for amen_row in c.fetchall():
            lang, key, value = amen_row
            if lang in ['ro', 'ru']:
                listing['amenities'][lang][key] = value
        
        # NOTE: standard_features removed - use features and amenities instead
        
        # Get map data
        c.execute('SELECT latitude, longitude, map_title FROM listing_map WHERE listing_id = ?', (listing_id,))
        map_row = c.fetchone()
        if map_row:
            listing['map_data'] = {
                'lat': map_row[0],
                'lng': map_row[1],
                'title': map_row[2]
            }
        else:
            listing['map_data'] = None
        
        conn.close()
        return listing
        
    except Exception as e:
        print(f"❌ Error retrieving listing from Mainframe.db: {e}")
        return None


def get_all_listings(status: str = 'active', db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Get all listings from Mainframe.db.
    
    Args:
        status: Filter by status ('active', 'archived', 'deleted', or 'all')
        db_path: Optional custom database path
        
    Returns:
        List of listing dictionaries (basic info only, not full data)
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        if status == 'all':
            c.execute('''
                SELECT id, url, title_ro, title_ru, price_json, address, 
                       folder_path, template_name, status, created_at, updated_at,
                       listing_type, sold, rented
                FROM listings
                ORDER BY created_at DESC
            ''')
        else:
            c.execute('''
                SELECT id, url, title_ro, title_ru, price_json, address,
                       folder_path, template_name, status, created_at, updated_at,
                       listing_type, sold, rented
                FROM listings
                WHERE status = ?
                ORDER BY created_at DESC
            ''', (status,))
        
        listings = []
        for row in c.fetchall():
            listing = dict(row)
            listing['price'] = json.loads(listing['price_json']) if listing.get('price_json') else {}
            del listing['price_json']
            listings.append(listing)
        
        conn.close()
        return listings
        
    except Exception as e:
        print(f"❌ Error retrieving listings from Mainframe.db: {e}")
        return []


def update_listing_status(listing_id: str, status: str, db_path: Optional[Path] = None) -> bool:
    """
    Update listing status.
    
    Args:
        listing_id: Listing ID
        status: New status ('active', 'archived', 'deleted')
        db_path: Optional custom database path
        
    Returns:
        True if successful
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        c.execute('''
            UPDATE listings 
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now(timezone.utc).isoformat(), listing_id))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error updating listing status: {e}")
        return False


def delete_listing_from_mainframe(listing_id: str, db_path: Optional[Path] = None) -> bool:
    """
    Permanently delete a listing from Mainframe.db.
    
    Args:
        listing_id: Listing ID to delete
        db_path: Optional custom database path
        
    Returns:
        True if successful
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        # CASCADE delete will handle related tables
        c.execute('DELETE FROM listings WHERE id = ?', (listing_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error deleting listing from Mainframe.db: {e}")
        return False


def save_poi_data_to_mainframe(listing_id: str, poi_data: Dict[str, List[Dict]], 
                              radius: int = 500, db_path: Optional[Path] = None,
                              verbose: bool = True) -> bool:
    """
    Save POI data for a listing to Mainframe.db.
    
    Args:
        listing_id: Listing ID
        poi_data: Dictionary of POI data by category
        radius: Search radius used for POI fetching
        db_path: Optional custom database path
        verbose: Whether to print progress messages
        
    Returns:
        True if successful
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        # Clear existing POI data for this listing
        c.execute('DELETE FROM listing_pois WHERE listing_id = ?', (listing_id,))
        
        # Insert new POI data for each category
        if verbose:
            print(f"\n  💾 Saving POI data to database:")
        for category, pois in poi_data.items():
            if pois:  # Only save categories that have POI data
                poi_json = json.dumps(pois, ensure_ascii=False)
                c.execute('''
                    INSERT INTO listing_pois (listing_id, category, poi_data, radius)
                    VALUES (?, ?, ?, ?)
                ''', (listing_id, category, poi_json, radius))
                if verbose:
                    print(f"     ✅ {category}: {len(pois)} POIs saved")
            else:
                # Log when a category has no POIs
                if verbose:
                    print(f"     ⚠️  {category}: 0 POIs (skipped)")
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving POI data to Mainframe.db: {e}")
        return False


def get_poi_data_from_mainframe(listing_id: str, db_path: Optional[Path] = None) -> Dict[str, List[Dict]]:
    """
    Retrieve POI data for a listing from Mainframe.db.
    
    Args:
        listing_id: Listing ID
        db_path: Optional custom database path
        
    Returns:
        Dictionary of POI data by category
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT category, poi_data, generated_at, radius 
            FROM listing_pois 
            WHERE listing_id = ?
            ORDER BY category
        ''', (listing_id,))
        
        rows = c.fetchall()
        conn.close()
        
        poi_data = {}
        for row in rows:
            category = row['category']
            poi_json = row['poi_data']
            poi_data[category] = json.loads(poi_json)
        
        return poi_data
        
    except Exception as e:
        print(f"❌ Error retrieving POI data from Mainframe.db: {e}")
        return {}


def get_poi_summary_from_mainframe(listing_id: str, db_path: Optional[Path] = None) -> Dict:
    """
    Get POI summary statistics for a listing.
    
    Args:
        listing_id: Listing ID
        db_path: Optional custom database path
        
    Returns:
        Dictionary with POI summary information
    """
    try:
        poi_data = get_poi_data_from_mainframe(listing_id, db_path)
        
        if not poi_data:
            return {'total_pois': 0, 'categories': {}}
        
        summary = {
            'total_pois': sum(len(pois) for pois in poi_data.values()),
            'categories': {}
        }
        
        for category, pois in poi_data.items():
            summary['categories'][category] = {
                'count': len(pois),
                'names': [poi['name'] for poi in pois[:3]]  # First 3 names as sample
            }
        
        return summary
        
    except Exception as e:
        print(f"❌ Error getting POI summary: {e}")
        return {'total_pois': 0, 'categories': {}}


def toggle_listing_sold(listing_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Toggle the sold status of a listing between 'yes' and 'no'.
    
    Args:
        listing_id: Listing ID
        db_path: Optional custom database path
        
    Returns:
        Dictionary with success status and new sold value
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        # Get current sold status
        c.execute('SELECT sold FROM listings WHERE id = ?', (listing_id,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return {'success': False, 'error': 'Listing not found'}
        
        current_sold = row[0] or 'no'
        new_sold = 'yes' if current_sold == 'no' else 'no'
        
        # Update sold status
        c.execute('''
            UPDATE listings 
            SET sold = ?, updated_at = ?
            WHERE id = ?
        ''', (new_sold, datetime.now(timezone.utc).isoformat(), listing_id))
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'sold': new_sold}
        
    except Exception as e:
        print(f"❌ Error toggling listing sold status: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================================
# Journal Entry Functions
# ============================================================================

def add_journal_entry(
    title: str,
    content: str,
    entry_type: str = 'log',
    listing_id: Optional[str] = None,
    user: Optional[str] = None,
    tags: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Add a new journal entry (log, comment, or note).
    
    Args:
        title: Entry title
        content: Entry content
        entry_type: Type of entry ('log', 'comment', 'note')
        listing_id: Optional listing ID to associate with
        user: Optional user who created the entry
        tags: Optional JSON string of tags
        db_path: Optional custom database path
        
    Returns:
        Dictionary with success status and entry ID
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO journal_entries (
                listing_id, entry_type, title, content, 
                created_at, updated_at, user, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing_id,
            entry_type,
            title,
            content,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            user,
            tags
        ))
        
        entry_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return {'success': True, 'id': entry_id}
        
    except Exception as e:
        print(f"❌ Error adding journal entry: {e}")
        return {'success': False, 'error': str(e)}


def get_journal_entries(
    listing_id: Optional[str] = None,
    entry_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Get journal entries with optional filtering.
    
    Args:
        listing_id: Optional filter by listing ID (None = all entries)
        entry_type: Optional filter by entry type
        limit: Maximum number of entries to return
        offset: Number of entries to skip
        db_path: Optional custom database path
        
    Returns:
        List of journal entry dictionaries
    """
    try:
        conn = init_mainframe_db(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = 'SELECT * FROM journal_entries WHERE 1=1'
        params = []
        
        if listing_id is not None:
            query += ' AND listing_id = ?'
            params.append(listing_id)
        
        if entry_type is not None:
            query += ' AND entry_type = ?'
            params.append(entry_type)
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        print(f"❌ Error getting journal entries: {e}")
        return []


def update_journal_entry(
    entry_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    entry_type: Optional[str] = None,
    tags: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Update an existing journal entry.
    
    Args:
        entry_id: Journal entry ID
        title: Optional new title
        content: Optional new content
        entry_type: Optional new entry type
        tags: Optional new tags
        db_path: Optional custom database path
        
    Returns:
        Dictionary with success status
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        updates = []
        params = []
        
        if title is not None:
            updates.append('title = ?')
            params.append(title)
        
        if content is not None:
            updates.append('content = ?')
            params.append(content)
        
        if entry_type is not None:
            updates.append('entry_type = ?')
            params.append(entry_type)
        
        if tags is not None:
            updates.append('tags = ?')
            params.append(tags)
        
        if not updates:
            conn.close()
            return {'success': False, 'error': 'No fields to update'}
        
        updates.append('updated_at = ?')
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(entry_id)
        
        query = f"UPDATE journal_entries SET {', '.join(updates)} WHERE id = ?"
        c.execute(query, params)
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except Exception as e:
        print(f"❌ Error updating journal entry: {e}")
        return {'success': False, 'error': str(e)}


def delete_journal_entry(entry_id: int, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Delete a journal entry.
    
    Args:
        entry_id: Journal entry ID
        db_path: Optional custom database path
        
    Returns:
        Dictionary with success status
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        c.execute('DELETE FROM journal_entries WHERE id = ?', (entry_id,))
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except Exception as e:
        print(f"❌ Error deleting journal entry: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================================
# Dashboard Edit Functions
# ============================================================================

def update_listing_fields(
    listing_id: str,
    updates: Dict[str, Any],
    user: Optional[str] = None,
    changed_fields: Optional[list] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Update specific fields of a listing from the dashboard.
    Automatically logs changes to journal and updates timestamp.
    
    OPTIMIZED: Only updates changed features/amenities instead of DELETE ALL + INSERT ALL.
    
    Args:
        listing_id: Listing ID to update
        updates: Dictionary of field names and new values
                 Supported fields: title_ro, title_ru, description_ro, description_ru,
                                  price_json, address, display_address, contact, template_name
        user: Optional username for journal entry
        changed_fields: Optional list of user-friendly field names that changed (for journal)
        db_path: Optional custom database path
        
    Returns:
        Dictionary with success status and updated fields
        
    Example:
        update_listing_fields('102528638', {
            'title_ro': 'New Title',
            'price_json': '{"EUR": "55,000 €"}',
            'contact': '+373 69 123 456'
        }, user='Admin', changed_fields=['title_ro', 'price'])
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        # Validate listing exists
        c.execute('SELECT id, title_ro FROM listings WHERE id = ?', (listing_id,))
        listing = c.fetchone()
        if not listing:
            conn.close()
            return {'success': False, 'error': f'Listing {listing_id} not found'}
        
        # Allowed fields for update
        allowed_fields = {
            'title_ro', 'title_ru', 'description_ro', 'description_ru',
            'price_json', 'address', 'display_address', 'geocoding_address',
            'contact', 'template_name', 'listing_type', 'property_type', 'sold', 'rented'
        }
        
        # Separate amenities and features from regular fields
        amenities_data = updates.pop('amenities', None)
        features_data = updates.pop('features', None)
        
        # Filter and validate updates
        valid_updates = {}
        for field, value in updates.items():
            if field in allowed_fields:
                valid_updates[field] = value
        
        if not valid_updates and not amenities_data and not features_data:
            conn.close()
            return {'success': False, 'error': 'No valid fields to update'}
        
        # Build UPDATE query for regular fields
        if valid_updates:
            set_clauses = [f"{field} = ?" for field in valid_updates.keys()]
            set_clauses.append("updated_at = ?")
            
            query = f"UPDATE listings SET {', '.join(set_clauses)} WHERE id = ?"
            params = list(valid_updates.values())
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(listing_id)
            
            c.execute(query, params)
        
        # Track DB operations for metrics
        db_ops = {'updates': 0, 'inserts': 0, 'deletes': 0}
        
        # Update amenities if provided (OPTIMIZED: diff-based update)
        if amenities_data:
            db_ops = _update_amenities_optimized(c, listing_id, amenities_data, db_ops)
        
        # Update features if provided (OPTIMIZED: diff-based update)
        if features_data:
            db_ops = _update_features_optimized(c, listing_id, features_data, db_ops)
        
        conn.commit()
        
        # Log performance metrics
        total_ops = db_ops['updates'] + db_ops['inserts'] + db_ops['deletes']
        if total_ops > 0:
            print(f"📊 DB Operations: {db_ops['updates']} UPDATEs, {db_ops['inserts']} INSERTs, {db_ops['deletes']} DELETEs")
        
        # Create journal entry with only changed fields
        if changed_fields and len(changed_fields) > 0:
            changes_summary = ', '.join(changed_fields)
        else:
            all_changes = list(valid_updates.keys())
            if amenities_data:
                all_changes.append('amenities')
            if features_data:
                all_changes.append('features')
            changes_summary = ', '.join(all_changes)
        
        add_journal_entry(
            title='edited',
            content=f"{changes_summary}",
            entry_type='log',
            listing_id=listing_id,
            user=user,
            db_path=db_path
        )
        
        conn.close()
        
        updated_count = len(valid_updates) + (1 if amenities_data else 0) + (1 if features_data else 0)
        updated_fields = list(valid_updates.keys())
        if amenities_data:
            updated_fields.append('amenities')
        if features_data:
            updated_fields.append('features')
            
        return {
            'success': True,
            'listing_id': listing_id,
            'updated_fields': updated_fields,
            'message': f'Successfully updated {updated_count} field(s)',
            'db_operations': db_ops
        }
        
    except Exception as e:
        print(f"❌ Error updating listing fields: {e}")
        return {'success': False, 'error': str(e)}


def _update_amenities_optimized(cursor, listing_id: str, amenities_data: Dict, db_ops: Dict) -> Dict:
    """
    Optimized amenities update - only changes what's different.
    
    Args:
        cursor: Database cursor
        listing_id: Listing ID
        amenities_data: New amenities data {'ro': {...}, 'ru': {...}}
        db_ops: Dictionary tracking database operations
        
    Returns:
        Updated db_ops dictionary
    """
    # Get existing amenities
    cursor.execute('''
        SELECT id, lang, amenity_key, amenity_value 
        FROM listing_amenities 
        WHERE listing_id = ?
    ''', (listing_id,))
    
    existing = {}
    for row in cursor.fetchall():
        key = (row[1], row[2])  # (lang, amenity_key)
        existing[key] = {'id': row[0], 'value': row[3]}
    
    # Build new amenities map
    new_amenities = {}
    for lang in ['ro', 'ru']:
        if lang in amenities_data and isinstance(amenities_data[lang], dict):
            for key, value in amenities_data[lang].items():
                new_amenities[(lang, key)] = str(value)
    
    # Find what to UPDATE, INSERT, DELETE
    existing_keys = set(existing.keys())
    new_keys = set(new_amenities.keys())
    
    to_update = existing_keys & new_keys  # Keys in both
    to_insert = new_keys - existing_keys   # Keys only in new
    to_delete = existing_keys - new_keys   # Keys only in existing
    
    # UPDATE changed values
    for key in to_update:
        if existing[key]['value'] != new_amenities[key]:
            cursor.execute('''
                UPDATE listing_amenities SET amenity_value = ? WHERE id = ?
            ''', (new_amenities[key], existing[key]['id']))
            db_ops['updates'] += 1
    
    # INSERT new amenities
    for key in to_insert:
        lang, amenity_key = key
        cursor.execute('''
            INSERT INTO listing_amenities (listing_id, lang, amenity_key, amenity_value)
            VALUES (?, ?, ?, ?)
        ''', (listing_id, lang, amenity_key, new_amenities[key]))
        db_ops['inserts'] += 1
    
    # DELETE removed amenities
    for key in to_delete:
        cursor.execute('DELETE FROM listing_amenities WHERE id = ?', (existing[key]['id'],))
        db_ops['deletes'] += 1
    
    return db_ops


def _update_features_optimized(cursor, listing_id: str, features_data: Dict, db_ops: Dict) -> Dict:
    """
    Optimized features update - only changes what's different.
    
    Args:
        cursor: Database cursor
        listing_id: Listing ID
        features_data: New features data {'ro': {section: {...}}, 'ru': {section: {...}}}
        db_ops: Dictionary tracking database operations
        
    Returns:
        Updated db_ops dictionary
    """
    # Get existing features
    cursor.execute('''
        SELECT id, lang, section, feature_key, feature_value 
        FROM listing_features 
        WHERE listing_id = ?
    ''', (listing_id,))
    
    existing = {}
    for row in cursor.fetchall():
        key = (row[1], row[2], row[3])  # (lang, section, feature_key)
        existing[key] = {'id': row[0], 'value': row[4]}
    
    # Build new features map
    new_features = {}
    for lang in ['ro', 'ru']:
        if lang in features_data and isinstance(features_data[lang], dict):
            for section, section_features in features_data[lang].items():
                if isinstance(section_features, dict):
                    for key, value in section_features.items():
                        new_features[(lang, section, key)] = str(value)
    
    # Find what to UPDATE, INSERT, DELETE
    existing_keys = set(existing.keys())
    new_keys = set(new_features.keys())
    
    to_update = existing_keys & new_keys  # Keys in both
    to_insert = new_keys - existing_keys   # Keys only in new
    to_delete = existing_keys - new_keys   # Keys only in existing
    
    # UPDATE changed values
    for key in to_update:
        if existing[key]['value'] != new_features[key]:
            cursor.execute('''
                UPDATE listing_features SET feature_value = ? WHERE id = ?
            ''', (new_features[key], existing[key]['id']))
            db_ops['updates'] += 1
    
    # INSERT new features
    for key in to_insert:
        lang, section, feature_key = key
        cursor.execute('''
            INSERT INTO listing_features (listing_id, lang, section, feature_key, feature_value)
            VALUES (?, ?, ?, ?, ?)
        ''', (listing_id, lang, section, feature_key, new_features[key]))
        db_ops['inserts'] += 1
    
    # DELETE removed features
    for key in to_delete:
        cursor.execute('DELETE FROM listing_features WHERE id = ?', (existing[key]['id'],))
        db_ops['deletes'] += 1
    
    return db_ops


def update_image_order(
    listing_id: str,
    image_order: List[str],
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Update the order of images for a listing.
    
    Args:
        listing_id: Listing ID to update
        image_order: List of local_path values in the new order (e.g., ['images/0.jpg', 'images/2.jpg', 'images/1.jpg'])
        db_path: Optional custom database path
        
    Returns:
        Dictionary with success status
    """
    try:
        conn = init_mainframe_db(db_path)
        c = conn.cursor()
        
        # Validate listing exists
        c.execute('SELECT id FROM listings WHERE id = ?', (listing_id,))
        if not c.fetchone():
            conn.close()
            return {'success': False, 'error': f'Listing {listing_id} not found'}
        
        # Step 1: Set all positions to negative temporary values to avoid UNIQUE constraint
        for i, local_path in enumerate(image_order):
            c.execute('''
                UPDATE listing_images 
                SET position = ? 
                WHERE listing_id = ? AND local_path = ?
            ''', (-(i + 1000), listing_id, local_path))
        
        # Step 2: Set final positions
        for new_position, local_path in enumerate(image_order):
            c.execute('''
                UPDATE listing_images 
                SET position = ? 
                WHERE listing_id = ? AND local_path = ?
            ''', (new_position, listing_id, local_path))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'listing_id': listing_id,
            'message': f'Successfully reordered {len(image_order)} images'
        }
        
    except Exception as e:
        print(f"❌ Error updating image order: {e}")
        return {'success': False, 'error': str(e)}
