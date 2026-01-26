# 🏠 RealAgent

**A comprehensive real estate listing management system with automated scraping, geocoding, and PWA generation.**

RealAgent is a Python-based platform that automates the entire workflow of creating, managing, and deploying real estate listings as Progressive Web Apps (PWAs). It scrapes property data from 999.md, enriches it with location intelligence, and generates beautiful, installable web applications for each listing.

---

## ✨ Key Features

### 🤖 Automated Data Collection
- **Web Scraping**: Extracts property data from 999.md (Moldovan real estate platform)
- **Bilingual Support**: Automatically fetches both Romanian and Russian versions
- **Image Processing**: Downloads and optimizes property images (WebP format)
- **Smart Parsing**: Extracts features, amenities, prices, and contact information

### 🗺️ Advanced Geocoding
- **Multi-Service Geocoding**: Uses Nominatim and Photon APIs with intelligent fallback
- **Address Intelligence**: Parses Moldovan addresses with district/street/building extraction
- **Confidence Scoring**: Evaluates geocoding accuracy (city: 25pts, street: 40pts, building: 35pts)
- **Interactive Correction**: Opens map overlay for manual address verification when confidence < 90%
- **Cyrillic Translation**: Handles Russian addresses with automatic transliteration

### 📍 Points of Interest (POI)
- **Pre-Generated Data**: Fetches nearby amenities during listing creation (no runtime API calls)
- **8 Categories**: Schools, kindergartens, hospitals, pharmacies, supermarkets, restaurants, banks, ATMs
- **Overpass API Integration**: Queries OpenStreetMap data within 500m radius
- **Smart Limits**: Max 10 POIs per category group (~50 total) for optimal performance

### 🎨 Template System
- **Luna Template**: Modern card-based design with dark mode support
- **Thunder Template**: Tinder-style swipeable interface with minimalist black/white design
- **Universal Builder**: Modular architecture for easy template creation
- **Bilingual UI**: Seamless language switching (Romanian ⇄ Russian)

### 💾 Centralized Database
- **SQLite (Mainframe.db)**: Single source of truth for all listings
- **Normalized Schema**: Separate tables for listings, images, features, amenities, POIs, and journal entries
- **Performance Optimized**: WAL mode, indexed queries, connection pooling
- **Migration Support**: Automatic schema updates for backward compatibility

### 📱 Progressive Web Apps (PWA)
- **Installable Listings**: Each property becomes a standalone app
- **Offline Support**: Service workers cache assets for offline viewing
- **App Shortcuts**: Quick actions for photos, map, and contact
- **Adaptive Icons**: Property images used as app icons
- **Push Notifications**: (Planned) Price updates and listing changes

### 🎛️ Dashboard Interface
- **Flask Web UI**: Modern dashboard for listing management
- **Real-time Editing**: Update titles, descriptions, prices, and addresses
- **Image Reordering**: Drag-and-drop image management
- **Journal System**: Track changes and add notes to listings
- **Statistics**: Comprehensive analytics (price trends, location distribution, property types)
- **QR Code Generation**: SVG/PNG QR codes for easy sharing
- **Bulk Operations**: Batch regenerate HTML, update statuses, archive listings

---

## 🏗️ Architecture

```
RealAgent/
├── Agent.py                    # Main scraping engine
├── Dashboard.py                # Flask web interface
├── Mainframe.db               # SQLite database
├── Helper/                    # Core modules
│   ├── database.py           # Database operations
│   ├── builder.py            # Universal template builder
│   ├── scraper_wrapper.py    # Dashboard scraping integration
│   ├── poi_fetcher.py        # POI data collection
│   ├── geoguess.py           # Address parsing & geocoding
│   ├── map_overlay.py        # Interactive map correction
│   ├── address_formatter.py  # Bilingual address formatting
│   ├── translations.py       # Feature translations
│   └── db_metrics.py         # Performance monitoring
├── Templates/                 # HTML templates
│   ├── Luna/                 # Modern card template
│   │   ├── Luna.html
│   │   ├── Luna.css
│   │   ├── builder.py
│   │   └── config.json
│   ├── Thunder/              # Swipeable template
│   │   ├── Thunder.html
│   │   ├── Thunder.css
│   │   ├── builder.py
│   │   └── config.json
│   └── Dashboard/            # Dashboard UI
├── pwa/                      # PWA infrastructure
│   ├── manifest_generator.py
│   ├── service-worker.js
│   └── assets/
└── Listings/                 # Generated listings
    └── [listing_id]/
        ├── index.html
        ├── manifest.json
        ├── [Template].css
        └── images/

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/RealAgent.git
cd RealAgent
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install Playwright browsers** (for web scraping)
```bash
playwright install chromium
```

4. **Initialize the database**
```bash
python -c "from Helper.database import init_mainframe_db; init_mainframe_db()"
```

### Quick Start

#### Scrape a Listing
```bash
python Agent.py
# Enter a 999.md listing URL when prompted
```

#### Launch Dashboard
```bash
python Dashboard.py
# Open http://localhost:5000 in your browser
```

#### Regenerate HTML
```bash
python regenerate_html.py --listing-id 102312333
# Or batch regenerate all listings:
python regenerate_html.py --batch
```

---

## 📖 Usage Guide

### Scraping Workflow

1. **Run Agent.py** and provide a 999.md URL
2. **Automatic Processing**:
   - Fetches Romanian and Russian versions
   - Downloads and optimizes images
   - Parses features and amenities
   - Geocodes address with confidence scoring
   - Opens interactive map if confidence < 90%
   - Fetches POI data (schools, hospitals, etc.)
   - Saves to Mainframe.db
   - Generates HTML with selected template
   - Creates PWA manifest

3. **Output**: `Listings/[id]/index.html` ready for deployment

### Dashboard Operations

#### View Listings
- Grid view with thumbnails and key details
- Filter by status (active/sold/rented)
- Sort by date, price, or location
- Quick actions: Edit, Archive, Delete, QR Code

#### Edit Listing
- Update title, description, price
- Correct address (triggers re-geocoding)
- Reorder images via drag-and-drop
- Change template (Luna ⇄ Thunder)
- Add journal notes

#### Statistics
- Total listings by type (sale/rent)
- Price analytics (min/max/avg, percentiles)
- Property type distribution
- Surface area averages
- Popular amenities
- Location heatmap

---

## 🛠️ Technologies

### Backend
- **Python 3.8+**: Core language
- **aiohttp**: Async HTTP client for scraping
- **Playwright**: Browser automation for JavaScript-heavy sites
- **BeautifulSoup4**: HTML parsing
- **Flask**: Web framework for dashboard
- **SQLite3**: Database engine

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **CSS3**: Modern styling with CSS variables
- **Leaflet.js**: Interactive maps
- **Service Workers**: PWA offline support

### APIs & Services
- **Nominatim**: OpenStreetMap geocoding
- **Photon**: Alternative geocoding service
- **Overpass API**: POI data from OpenStreetMap

### Image Processing
- **Pillow (PIL)**: Image optimization and WebP conversion

### Geospatial
- **Folium**: Interactive map generation for address correction

---

## 📊 Database Schema

### Core Tables
- **listings**: Main property data (title, description, price, address, status)
- **listing_images**: Image URLs and local paths with ordering
- **listing_features**: Property characteristics (rooms, surface, floor, etc.)
- **listing_amenities**: Available amenities (parking, elevator, balcony, etc.)
- **listing_map**: Geocoded coordinates and map titles
- **listing_pois**: Pre-generated POI data by category
- **journal_entries**: Change logs and notes

### Key Features
- Foreign key constraints with CASCADE delete
- Indexed columns for fast queries
- WAL mode for concurrent access
- Automatic timestamp tracking

---

## 🎨 Template Development

### Creating a New Template

1. **Create template folder**
```bash
mkdir -p Templates/MyTemplate
```

2. **Create required files**
```
Templates/MyTemplate/
├── MyTemplate.html      # HTML template with {placeholders}
├── MyTemplate.css       # Stylesheet
├── builder.py           # Builder functions
└── config.json          # Template metadata
```

3. **Implement builder.py**
```python
def build_mytemplate_html(listing_id, template_path, base_url=''):
    from Helper.database import get_listing_from_mainframe
    
    listing_data = get_listing_from_mainframe(listing_id)
    # Build placeholders dict
    placeholders = {
        'title': listing_data['title_ro'],
        'price': listing_data['price'],
        # ... more placeholders
    }
    
    # Load and populate template
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    for key, value in placeholders.items():
        template = template.replace(f'{{{key}}}', str(value))
    
    return template
```

4. **Register in Helper/builder.py**
```python
from Templates.MyTemplate.builder import build_mytemplate_html

TEMPLATE_REGISTRY['mytemplate'] = {
    'builder': build_mytemplate_html,
    'template_path': project_root / 'Templates' / 'MyTemplate' / 'MyTemplate.html',
    'css_path': project_root / 'Templates' / 'MyTemplate' / 'MyTemplate.css',
    'descriptions': {
        'en': 'My custom template',
        'ro': 'Șablonul meu personalizat',
        'ru': 'Мой пользовательский шаблон'
    }
}
```

---

## 🔧 Configuration

### Environment Variables
```bash
# Base URL for deployed listings (for Open Graph tags)
BASE_URL="https://yourdomain.com"

# Database path (optional, defaults to ./Mainframe.db)
DB_PATH="/path/to/Mainframe.db"

# Geocoding verbosity
VERBOSE_GEOCODING=False
```

### Dashboard Settings
Edit `Dashboard.py`:
```python
# Port configuration
app.run(host='0.0.0.0', port=5000)

# Database path
DB_PATH = Path(__file__).parent / "Mainframe.db"

# Listings directory
LISTINGS_DIR = Path(__file__).parent / "Listings"
```

### Template Selection
Default template in `Helper/builder.py`:
```python
DEFAULT_TEMPLATE = 'luna'  # or 'thunder'
```

---

## 📈 Performance

### Geocoding
- **Confidence Scoring**: Ensures accurate location data
- **Multi-Service Fallback**: Nominatim → Photon → Cache
- **Interactive Correction**: Manual verification for low-confidence results
- **Caching**: Stores geocoded addresses to avoid redundant API calls

### POI Fetching
- **Pre-Generation**: Fetches during listing creation (not at runtime)
- **Optimized Queries**: Combined Overpass queries reduce API calls
- **Smart Limits**: 10 POIs per category group, ~50 total
- **45s Timeout**: Ensures responsive scraping workflow

### Database
- **WAL Mode**: Concurrent reads without blocking
- **Indexed Queries**: Fast lookups on listing_id, status, created_at
- **Connection Pooling**: Reuses connections in dashboard
- **Metrics Tracking**: Built-in performance monitoring (db_metrics.py)

---

## 🌍 Localization

### Supported Languages
- **Romanian (ro)**: Primary language
- **Russian (ru)**: Full translation support

### Translation System
- **Feature Translations**: `Helper/translations.py` maps Romanian ⇄ Russian
- **Address Formatting**: `Helper/address_formatter.py` handles bilingual addresses
- **UI Labels**: Templates include both languages with JavaScript switching
- **Cyrillic Detection**: Automatic detection and transliteration

### Adding Translations
Edit `Helper/translations.py`:
```python
PROPERTY_FEATURE_TRANSLATIONS = {
    'Количество комнат': 'Număr de camere',
    'Общая площадь': 'Suprafața totală',
    # Add more translations
}
```

---

## 🔒 Security Considerations

### Current Implementation
- **Local SQLite**: No remote database access
- **No Authentication**: Dashboard runs on localhost
- **File System Access**: Direct access to Listings folder

### Production Recommendations
1. **Add Authentication**: Implement login system for dashboard
2. **HTTPS**: Use SSL certificates for production deployment
3. **Input Validation**: Sanitize all user inputs
4. **Rate Limiting**: Protect scraping endpoints
5. **Database Backups**: Regular automated backups of Mainframe.db
6. **Access Control**: Restrict file system permissions

---

## 🐛 Troubleshooting

### Scraping Issues
**Problem**: "Failed to fetch listing data"
- Check internet connection
- Verify 999.md URL format
- Ensure Playwright browsers are installed: `playwright install chromium`

**Problem**: "Geocoding failed"
- Address may be incomplete or invalid
- Use interactive map to manually correct location
- Check Nominatim/Photon API availability

### Dashboard Issues
**Problem**: "Database locked"
- Close other connections to Mainframe.db
- Check for zombie processes: `ps aux | grep python`
- Restart dashboard: `python Dashboard.py`

**Problem**: "Images not loading"
- Verify images exist in `Listings/[id]/images/`
- Check file permissions
- Clear browser cache

### Template Issues
**Problem**: "Template not found"
- Verify template exists in `Templates/` folder
- Check TEMPLATE_REGISTRY in `Helper/builder.py`
- Ensure builder.py is properly imported

---

## 🗺️ Roadmap

### Planned Features
- [ ] **Multi-Site Support**: Scrape from additional real estate platforms
- [ ] **Push Notifications**: Alert users to price changes and updates
- [ ] **Authentication System**: Secure dashboard with user accounts
- [ ] **Cloud Hosting**: Automatic deployment of PWA listings
- [ ] **AI Integration**: Use LLMs to parse unstructured listing data
- [ ] **Mobile App**: Native iOS/Android apps for listing management
- [ ] **Analytics Dashboard**: Track views, installs, and user engagement
- [ ] **CRM Integration**: Connect with real estate CRM systems
- [ ] **Virtual Tours**: 360° photo integration
- [ ] **Mortgage Calculator**: Built-in financing tools

### Template Roadmap
- [ ] **Nova Template**: Minimalist single-page design
- [ ] **Apex Template**: Luxury property showcase
- [ ] **Grid Template**: Pinterest-style masonry layout
- [ ] **Video Template**: Video-first property tours

---

**Built with ❤️ for the Moldovan real estate market**
