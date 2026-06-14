# RealAgent — Go Migration Plan

## Goal

Rewrite the Python Flask dashboard into a single Go binary (~15MB) that embeds all templates, static assets, and the SQLite database — zero runtime dependencies, one file to deploy.

**Why Go:** ~15MB binary, static linking, built-in HTTP server (`net/http`), embedded SQLite (`modernc.org/sqlite`), native HTML templating (`html/template`), trivial cross-compilation. No Python runtime, no virtualenv, no pip install.

**No Playwright needed.** Phone numbers are embedded in the Next.js RSC payload (`self.__next_f.push(...)`) in the raw HTML. Plain HTTP GET + regex extracts `phone_numbers:["373XXXXXXXX"]`. Go can scrape 100% of listing data with no browser.

**Templates stay as-is.** All HTML/CSS from the existing codebase gets embedded into the Go binary via `//go:embed`. No rewrite of the frontend.

---

## Architecture Comparison

| Component | Python (current) | Go (target) |
|---|---|---|
| HTTP server | Flask (dev server) | `net/http` |
| Database | SQLite via `sqlite3` | `modernc.org/sqlite` (pure Go, no CGO) |
| ORM | Raw SQL + fetchall | Raw SQL via `database/sql` |
| Templates | Jinja2 | `html/template` |
| Scraping | `requests` + `BeautifulSoup` | `net/http` + `golang.org/x/net/html` |
| Geocoding | `requests` to OSM Nominatim | `net/http` to OSM Nominatim |
| Overpass API | `requests` to Overpass | `net/http` to Overpass |
| Image download | `requests` | `net/http` |
| Image conversion | `Pillow` | `golang.org/x/image` + WebP encoder |
| QR generation | `qrcode` | `skip2/go-qrcode` |
| Translations | Python dict | Go map — trivial port |
| Concurrency | Threading (FetchAll) | Goroutines (native) |
| Build artifact | `python3 Dashboard.py` | Single binary |
| Dependencies | 20+ pip packages | Go modules (`go mod tidy`) |

---

## Project Structure (Go)

```
RealAgent/
├── main.go                  # Entry point, server init
├── go.mod / go.sum
├── cmd/
│   ├── dashboard/          # Dashboard server
│   │   └── main.go
│   ├── scraper/            # CLI scraper
│   │   └── main.go
│   └── regenerate/         # HTML regeneration CLI
│       └── main.go
├── internal/
│   ├── database/           # DB init, migrations, queries
│   │   ├── db.go
│   │   ├── listings.go
│   │   ├── users.go
│   │   ├── features.go
│   │   ├── active_subscriptions.go
│   │   └── settings.go
│   ├── scraper/            # Core scraping engine
│   │   ├── scraper.go      # HTTP client, fetch listing
│   │   ├── parser.go       # HTML parse → Listing struct
│   │   ├── phone.go        # RSC phone extraction
│   │   ├── geocoder.go     # OSM Nominatim geocoding
│   │   ├── translator.go   # Feature translations RO↔RU
│   │   ├── downloader.go   # Image download + WebP convert
│   │   └── types.go        # Shared types
│   ├── api/                # HTTP handlers
│   │   ├── server.go       # Server setup, middleware
│   │   ├── auth.go         # Login/logout/session
│   │   ├── listings.go     # CRUD endpoints
│   │   ├── search.go       # Express search
│   │   ├── sync.go         # Sync/refresh
│   │   ├── tags.go         # Tags/sections
│   │   ├── features.go     # Feature templates
│   │   ├── regenerate.go   # HTML regen trigger
│   │   ├── settings.go     # Settings endpoints
│   │   ├── users.go        # User management
│   │   ├── media.go        # Image serving
│   │   └── qr.go           # QR code generation
│   ├── templates/          # Go template rendering
│   │   ├── render.go       # Template rendering helpers
│   │   └── functions.go    # Template function map
│   ├── builder/            # HTML listing builder
│   │   ├── builder.go      # Template registry + build orchestration
│   │   ├── luna.go         # Luna listing builder
│   │   └── thunder.go      # Thunder listing builder
│   ├── poi/                # POI fetching via Overpass
│   │   ├── fetcher.go
│   │   └── types.go
│   └── pwa/                # PWA manifest gen
│       └── manifest.go
├── web/                    # Embedded templates & assets
│   ├── templates/          # Go html/template files
│   │   ├── dashboard/      # Dashboard UI templates
│   │   │   ├── layout.html
│   │   │   ├── login.html
│   │   │   ├── listings.html
│   │   │   └── ...
│   │   ├── luna/           # Luna listing template
│   │   │   └── template.html
│   │   ├── thunder/        # Thunder listing template
│   │   │   └── template.html
│   │   └── ...
│   ├── static/             # Static assets (CSS, JS, icons)
│   └── pwa/                # PWA files
└── listings/               # Generated listing output (runtime)
```

---

## Phase 0: Foundation

**Estimated: 1 session**

### Steps
1. `go mod init realagent`
2. Install dependencies:
   - `modernc.org/sqlite` (CGo-free SQLite)
   - `golang.org/x/net/html` (HTML parsing)
   - `golang.org/x/image` (image processing)
   - `golang.org/x/crypto` (bcrypt for passwords)
   - `github.com/skip2/go-qrcode` (QR generation)
   - `github.com/gorilla/sessions` (session management)
     or use `net/http` + cookies directly
   - `github.com/gorilla/mux` (or use `net/http` ServeMux in Go 1.22+)
3. Set up project structure per above
4. Create `main.go` that starts HTTP server on `:5000`
5. Embed all existing HTML/CSS assets with `//go:embed`

### Key Decisions
- **Router:** Go 1.22+ `net/http` now supports path params (`GET /listings/{id}`). Use stdlib, no third-party router needed.
- **Sessions:** Use encrypted cookies (stdlib `gorilla/securecookie` or manual HMAC). No Redis needed.
- **Asset embedding:** `//go:embed web/templates/*.html web/static/*` at compile time.
- **SQLite driver:** `modernc.org/sqlite` — pure Go, no CGo, cross-compiles trivially.

---

## Phase 1: Database Layer

**Estimated: 1 session**

### Schema (unchanged, same as current Mainframe.db)

Tables to migrate (from `Helper/database.py`):
- **listings** (39 cols) — main listing data
- **features** — feature name cache
- **users** — admin accounts
- **active_subscriptions** — sync schedules
- **settings** — key-value config

### Implementation pattern

```go
// internal/database/db.go
package database

import (
    "database/sql"
    _ "modernc.org/sqlite"
)

type DB struct {
    *sql.DB
}

func Open(path string) (*DB, error) {
    db, err := sql.Open("sqlite", path)
    if err != nil { return nil, err }
    // Enable WAL mode
    db.Exec("PRAGMA journal_mode=WAL")
    return &DB{db}, nil
}
```

### What to port
- `init_database()` → `DB.Migrate()` — create tables if not exist
- `insert_listing()`, `update_listing()`, `delete_listing()` → typed methods
- `get_listing()`, `get_all_listings()` → with filters, pagination, search
- `add_user()`, `verify_user()` → bcrypt hashing
- `get_next_listing_to_sync()` → priority queue logic
- All CRUD: 200-300 lines of Go vs 1700 lines of Python

**Complex queries:**
- `express_search()`: full-text search across title, description, address, phone
- `get_listings_by_section()`: section/pagination
- `get_listings_by_tag()`: tag filtering
- `sync_get_tags()`: distinct sections/tags for filter UI

---

## Phase 2: Scraping Engine

**Estimated: 2 sessions**

### Core flow (from `Agent.py`)

```
fetch_listing_data(url)
  → HTTP GET listing page
  → Parse with golang.org/x/net/html
  → Extract: title, price, description, images, features, phone
  → Geocode address via OSM Nominatim
  → Download + convert images to WebP
  → Apply translation mapping (RO↔RU)
  → Return ListingData struct
  → DB upsert
```

### Key components to port

#### 1. HTTP Client (`internal/scraper/scraper.go`)
- Configurable timeout, user-agent rotation
- Retry with backoff (3 attempts)
- Cookie handling if needed

#### 2. HTML Parser (`internal/scraper/parser.go`)
- Parse 999.md listing page DOM
- Extract structured fields:
  - Title from `<h1>` / meta
  - Price from price container
  - Description from description div
  - Image URLs from gallery
  - Features from attributes table
  - Category/section from breadcrumb
  - Coordinates from data attributes or URL

#### 3. Phone Extractor (`internal/scraper/phone.go`) — ✓ WORKING
- Search raw HTML for `phone_numbers":["373`
- Extract digits between quotes
- Strip leading `373`, format as `+373 XX XXX XXX`

#### 4. Geocoder (`internal/scraper/geocoder.go`)
- HTTP GET to `https://nominatim.openstreetmap.org/search`
- Parse JSON response for lat/lon
- Respect rate limit (1 req/sec)
- Use Go `time.Ticker` for rate limiting

#### 5. Translator (`internal/scraper/translator.go`)
- Port Romanian↔Russian feature map from `Helper/translations.py`
- ~50 key-value pairs — trivial Go map

#### 6. Image Downloader (`internal/scraper/downloader.go`)
- HTTP GET each image URL
- Convert to WebP via `golang.org/x/image/webp` encoder
- Save to `listings/{id}/` directory
- Generate thumbnails (resize + WebP encode)

### Data Types (`internal/scraper/types.go`)

```go
type ListingData struct {
    URL           string
    Title         string
    Price         string
    PriceEUR      string
    Description   string
    Phone         string
    Images        []string
    Features      []Feature
    Section       string
    Address       string
    Latitude      float64
    Longitude     float64
    // ... 30+ fields matching DB columns
}

type Feature struct {
    Name  string
    Value string
}
```

### Concurrency (FetchAll replacement)

```go
func (s *Scraper) FetchAll(urls []string, workers int) chan Result {
    results := make(chan Result)
    sem := make(chan struct{}, workers)
    
    go func() {
        var wg sync.WaitGroup
        for _, url := range urls {
            wg.Add(1)
            sem <- struct{}{}
            go func(u string) {
                defer wg.Done()
                defer func() { <-sem }()
                results <- s.FetchOne(u)
            }(url)
        }
        wg.Wait()
        close(results)
    }()
    
    return results
}
```

---

## Phase 3: API Server

**Estimated: 1 session**

### What to port from `Dashboard.py`

Auth:
- `POST /login` → session cookie set
- `GET /logout` → session clear
- Middleware: redirect to login if no session

Listings:
- `GET /` — dashboard page
- `GET /listings` — listing table (paginated, searchable)
- `GET /listings/{id}` — listing detail
- `POST /listings` — create listing by URL
- `POST /listings/{id}/sync` — sync single listing
- `POST /listings/{id}/delete` — delete listing
- `POST /listings/add` — add by URL (dashboard form)

Sync:
- `POST /sync/start` — begin batch sync
- `GET /sync/status` — progress polling
- `POST /sync/stop` — cancel batch sync

Search:
- `GET /search` — express search endpoint
- `POST /search` — search with filters

Settings:
- `GET /settings` — settings page
- `POST /settings` — save settings
- `POST /settings/test_phone` — test phone number

Users:
- `GET /users` — user management page
- `POST /users` — create user
- `POST /users/{id}/delete` — delete user
- `POST /users/{id}/password` — change password

Tags/Sections:
- `GET /sections` — section management
- `POST /sections` — create section
- `POST /sections/{id}/delete` — delete section

Media:
- `GET /media/{type}/{filename}` — serve listing images
- `GET /qr/{id}` — generate QR code for listing URL

### Session handling

```go
func (s *Server) authMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        cookie, err := r.Cookie("session")
        if err != nil || !s.validateSession(cookie.Value) {
            http.Redirect(w, r, "/login", http.StatusSeeOther)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

### Sync status polling

Current Flask implementation uses a JSON file for progress. Go version:
- Use a shared `sync.Mutex`-protected status struct
- `/sync/status` reads the struct, returns JSON
- No file I/O, faster, thread-safe

---

## Phase 4: Template System

**Estimated: 1 session**

### Go `html/template` vs Jinja2

| Feature | Jinja2 | Go html/template |
|---|---|---|
| Template inheritance | `{% extends %}` / `{% block %}` | `{{template "name" .}}` |
| Variables | `{{ var }}` | `{{ .Var }}` |
| Loops | `{% for x in list %}` | `{{range .List}} {{.}} {{end}}` |
| Conditionals | `{% if %}` | `{{if .Cond}}` |
| Filters | `{{ x\|lower }}` | `{{.X \| lowerFunc}}` |
| Auto-escape | HTML-escaped by default | HTML-escaped by default |

### Porting strategy

The main dashboard template (`dashboard.html`, 503KB) is the biggest piece of work. Three approaches:

**Option A: Port to Go template syntax** — Full rewrite of all templates. Cleanest result, most work.

**Option B: Serve original HTML, inject data via JS fetch()** — Minimal template change. Server returns JSON, JS renders. Fastest migration.

**Option C: Hybrid** — Port the Django/Jinja2 control structures to Go template syntax while keeping all HTML/ CSS identical. ~1-2 hours of find-replace.

**Recommended: Option A** — Port to Go templates. The template logic is mostly loops (listing rows) and conditionals (show/hide). Go's `html/template` maps directly. The 503KB size is mostly static HTML + CSS.

### Listing Builder (port from `Helper/builder.py`)

- Luna builder: ~70 lines Python → Go struct + template render
- Thunder builder: ~40 lines Python → Go struct + template render  
- Embed the HTML template files directly
- Build method: load template → populate struct → render to string

### POI integration (port from `Helper/poi_fetcher.py`)

- Overpass API query: same HTTP call in Go
- Parse GeoJSON response
- Embed POI markers in listing HTML
- Use `golang.org/x/net/html` or `encoding/json`

---

## Phase 5: Dashboard Frontend (Static Assets)

**Estimated: 1 session**

### What to embed
- `Templates/Dashboard/` — all dashboard HTML templates
- Static CSS/JS (table sorting, modal, AJAX handlers)
- PWA service worker, manifest
- All listing templates

### Serving images
- Generated listing images stored on disk in `listings/{id}/`
- Server serves them from filesystem
- Go's `http.FileServer` + `http.StripPrefix`

### QR Code generation
- Port from `Dashboard.py` QR section
- Use `github.com/skip2/go-qrcode`
- Generate on-the-fly or cache to disk

---

## Phase 6: PWA Support

**Estimated: 0.5 session**

- Embed `pwa/` files
- Service worker registration endpoint
- Manifest generation with dynamic name/icon
- Same logic as current Flask implementation, in Go

---

## Migration Strategy

### Approach: Parallel implementation, then cut over

```
Week 1 (Session A):
  Day 1: Go project init, DB layer, embed assets, port ~50% of API endpoints
  Day 2: Scraping engine, phone extraction, geocoding, image download

Week 2 (Session B):
  Day 1: Port remaining API endpoints, auth, sessions
  Day 2: Port templates (dashboard.html → Go template), listing builder

Week 3 (Session C):
  Day 1: Port POI fetcher, PWA, QR gen, test coverage
  Day 2: Integration testing, parallel run with Python version
  
Cut over:
  - Stop Flask app
  - Start Go binary
  - Same SQLite database (no migration needed)
  - Same listing output directory
```

### Risk Areas

| Risk | Mitigation |
|---|---|
| XSS via template injection | Go `html/template` auto-escapes by default |
| SQLite concurrency | WAL mode + `database/sql` connection pool |
| Geocoding rate limits | `time.Ticker` for 1 req/sec |
| Image processing (WebP) | `golang.org/x/image` encoder — slower than C libwebp but no CGo |
| Phone format changes | Regex-based extraction, monitor for 999.md RSC format changes |
| Session security | HMAC-signed cookies, HttpOnly, SameSite=Strict |

### Why Not Rust

Go gives us:
- Faster development (days vs weeks)
- Simpler toolchain (install Go → go build → binary)
- Built-in `net/http`, `html/template`, `database/sql`
- Pure Go SQLite (no CGo)
- ~15MB binary (Rust would be ~5MB but costs more dev time)
- Easier to maintain as solo dev

If scraping speed were the bottleneck, Rust would win. But scraping is I/O-bound (HTTP latency), not CPU-bound. Go goroutines handle hundreds of concurrent fetches just as well as Rust async.

---

## Quick Start (Once Implemented)

```bash
# Build
go build -o realagent ./cmd/dashboard

# Run (SQLite DB created automatically)
./realagent -port 5000 -db Mainframe.db

# Open http://localhost:5000
# Default login: admin / admin123
```

### Docker (for production)

```dockerfile
FROM alpine:latest
COPY realagent /app/
EXPOSE 5000
CMD ["/app/realagent", "-port", "5000", "-db", "/data/Mainframe.db"]
```

```bash
docker build -t realagent .
docker run -p 5000:5000 -v data:/data realagent
```

---

## Appendix: Full File Map (Current Python → Go equivalences)

| Python File | Go Package | Lines (Py) | Complexity |
|---|---|---|---|
| `Dashboard.py` | `internal/api/` | 3320 | High — port as 10 handler files |
| `Agent.py` | `internal/scraper/` | 2732 | Medium — mostly HTTP + parse |
| `Helper/database.py` | `internal/database/` | 1707 | Medium — SQL port |
| `Helper/poi_fetcher.py` | `internal/poi/` | 648 | Low — HTTP + JSON parse |
| `Helper/builder.py` | `internal/builder/` | 353 | Low — struct + template |
| `Helper/geoguess.py` | `internal/scraper/geocoder.go` | 380 | Low — HTTP + JSON parse |
| `Helper/translations.py` | `internal/scraper/translator.go` | 50 | Trivial — Go map |
| `Helper/scraper_wrapper.py` | `internal/scraper/` | 450 | Low — delegation layer |
| `regenerate_html.py` | `cmd/regenerate/` | 358 | Low — CLI orchestration |
| `Templates/Dashboard/dashboard.html` | `web/templates/dashboard/` | 503KB | High volume, low complexity |
| `Templates/Luna/` | `web/templates/luna/` | ~300 | Low — static HTML |
| `Templates/Thunder/` | `web/templates/thunder/` | ~200 | Low — static HTML |
| `pwa/` | `web/pwa/` | ~100 | Low — static files |
| `seed_*.py` | `cmd/seed/` | ~200 | Low — CLI data load |
