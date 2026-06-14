package database

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"log"

	_ "modernc.org/sqlite"
)

// sha256Hex returns SHA-256 hex digest of a string.
func sha256Hex(s string) string {
	h := sha256.Sum256([]byte(s))
	return hex.EncodeToString(h[:])
}

// OpenDB opens SQLite database with WAL mode enabled.
func OpenDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	db.Exec("PRAGMA journal_mode=WAL")
	db.Exec("PRAGMA busy_timeout=5000")
	db.Exec("PRAGMA foreign_keys=ON")

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("ping db: %w", err)
	}
	return db, nil
}

// InitSchema creates all tables and indexes if they don't exist.
func InitSchema(db *sql.DB) error {
	schemas := []string{
		`CREATE TABLE IF NOT EXISTS listings (
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
			user_corrected_address INTEGER DEFAULT 0,
			created_by TEXT DEFAULT 'admin',
			updated_by TEXT DEFAULT 'admin',
			sold TEXT DEFAULT 'no' CHECK(sold IN ('yes', 'no')),
			rented TEXT DEFAULT 'no' CHECK(rented IN ('yes', 'no')),
			listing_type TEXT DEFAULT 'for_sale' CHECK(listing_type IN ('for_rent', 'for_sale', 'both')),
			property_type TEXT DEFAULT 'apartment' CHECK(property_type IN ('apartment', 'house', 'commercial', 'other'))
		)`,
		`CREATE TABLE IF NOT EXISTS listing_images (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			listing_id TEXT NOT NULL,
			image_url TEXT,
			local_path TEXT,
			position INTEGER NOT NULL,
			FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
			UNIQUE(listing_id, position)
		)`,
		`CREATE TABLE IF NOT EXISTS listing_features (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			listing_id TEXT NOT NULL,
			lang TEXT NOT NULL CHECK(lang IN ('en', 'ro', 'ru')),
			section TEXT,
			feature_key TEXT,
			feature_value TEXT,
			FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
		)`,
		`CREATE TABLE IF NOT EXISTS listing_map (
			listing_id TEXT PRIMARY KEY,
			latitude REAL,
			longitude REAL,
			map_title TEXT,
			FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
		)`,
		`CREATE TABLE IF NOT EXISTS listing_amenities (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			listing_id TEXT NOT NULL,
			lang TEXT NOT NULL CHECK(lang IN ('en', 'ro', 'ru')),
			amenity_key TEXT,
			amenity_value TEXT,
			FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
		)`,
		`CREATE TABLE IF NOT EXISTS listing_pois (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			listing_id TEXT NOT NULL,
			category TEXT NOT NULL,
			poi_data TEXT NOT NULL,
			generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
			radius INTEGER DEFAULT 500,
			FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
			UNIQUE(listing_id, category)
		)`,
		`CREATE TABLE IF NOT EXISTS journal_entries (
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
		)`,
		`CREATE TABLE IF NOT EXISTS geocode_cache (
			key TEXT PRIMARY KEY,
			lat REAL NOT NULL,
			lng REAL NOT NULL,
			title TEXT,
			created_at TEXT DEFAULT CURRENT_TIMESTAMP
		)`,
		`CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT UNIQUE NOT NULL,
			password_hash TEXT NOT NULL,
			full_name TEXT,
			role TEXT DEFAULT 'agent' CHECK(role IN ('admin', 'agent', 'viewer')),
			active INTEGER DEFAULT 1,
			created_at TEXT DEFAULT CURRENT_TIMESTAMP,
			last_login TEXT
		)`,
	}

	indexes := []string{
		"CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status)",
		"CREATE INDEX IF NOT EXISTS idx_listings_created ON listings(created_at)",
		"CREATE INDEX IF NOT EXISTS idx_images_listing ON listing_images(listing_id, position)",
		"CREATE INDEX IF NOT EXISTS idx_features_listing ON listing_features(listing_id, lang)",
		"CREATE INDEX IF NOT EXISTS idx_amenities_listing ON listing_amenities(listing_id, lang)",
		"CREATE INDEX IF NOT EXISTS idx_pois_listing ON listing_pois(listing_id, category)",
		"CREATE INDEX IF NOT EXISTS idx_journal_listing ON journal_entries(listing_id)",
		"CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at DESC)",
		"CREATE INDEX IF NOT EXISTS idx_geocode_cache_created ON geocode_cache(created_at DESC)",
		"CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
		"CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)",
	}

	for _, s := range schemas {
		if _, err := db.Exec(s); err != nil {
			return fmt.Errorf("schema: %w\nSQL: %s", err, s)
		}
	}
	for _, idx := range indexes {
		if _, err := db.Exec(idx); err != nil {
			return fmt.Errorf("index: %w\nSQL: %s", err, idx)
		}
	}
	return nil
}

// SeedDefaultUser creates the default admin user if no users exist.
func SeedDefaultUser(db *sql.DB) error {
	var count int
	db.QueryRow("SELECT COUNT(*) FROM users").Scan(&count)
	if count > 0 {
		return nil
	}
	// Default: admin / admin123 (SHA-256)
	hash := sha256Hex("admin123")
	_, err := db.Exec(`INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)`,
		"admin", hash, "Administrator", "admin")
	if err != nil {
		return fmt.Errorf("seed user: %w", err)
	}
	log.Println("✅ Created default admin user (admin/admin123)")
	return nil
}
