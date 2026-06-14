package database

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// parsePrice extracts a human-readable price string from JSON price data.
func parsePrice(priceJSON string) string {
	if priceJSON == "" || priceJSON == "{}" {
		return ""
	}
	var prices map[string]string
	if err := json.Unmarshal([]byte(priceJSON), &prices); err != nil {
		return priceJSON
	}
	// Prefer EUR
	if v, ok := prices["EUR"]; ok && v != "" {
		if n, err := strconv.ParseFloat(v, 64); err == nil {
			if n >= 1000 {
				return fmt.Sprintf("€%.0fK", n/1000)
			}
			return fmt.Sprintf("€%s", formatPrice(v))
		}
		return "€" + v
	}
	// Fallback to MDL
	if v, ok := prices["MDL"]; ok && v != "" {
		return v + " MDL"
	}
	// Return first available
	for _, v := range prices {
		return v
	}
	return priceJSON
}

func formatPrice(s string) string {
	n, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return s
	}
	return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.0f", n), "0"), ".")
}

// ─── Data Types ─────────────────────────────────────────────────────

type ListingBasic struct {
	ID           string `json:"id"`
	URL          string `json:"url"`
	TitleRO      string `json:"title_ro"`
	TitleRU      string `json:"title_ru"`
	PriceJSON    string `json:"price_json"`
	Price        string `json:"price"`
	Address      string `json:"address"`
	FolderPath   string `json:"folder_path"`
	TemplateName string `json:"template_name"`
	Status       string `json:"status"`
	ListingType  string `json:"listing_type"`
	Sold         string `json:"sold"`
	Rented       string `json:"rented"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
}

type ListingImage struct {
	ID        int    `json:"id"`
	ListingID string `json:"listing_id"`
	ImageURL  string `json:"image_url"`
	LocalPath string `json:"local_path"`
	Position  int    `json:"position"`
}

type ListingFeature struct {
	ID           int    `json:"id"`
	ListingID    string `json:"listing_id"`
	Lang         string `json:"lang"`
	Section      string `json:"section"`
	FeatureKey   string `json:"feature_key"`
	FeatureValue string `json:"feature_value"`
}

type ListingAmenity struct {
	ID           int    `json:"id"`
	ListingID    string `json:"listing_id"`
	Lang         string `json:"lang"`
	AmenityKey   string `json:"amenity_key"`
	AmenityValue string `json:"amenity_value"`
}

type ListingMap struct {
	ListingID string  `json:"listing_id"`
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
	MapTitle  string  `json:"map_title"`
}

type ListingPOI struct {
	ID          int    `json:"id"`
	ListingID   string `json:"listing_id"`
	Category    string `json:"category"`
	POIData     string `json:"poi_data"`
	GeneratedAt string `json:"generated_at"`
	Radius      int    `json:"radius"`
}

type ListingFull struct {
	ListingBasic
	DescriptionRO string          `json:"description_ro"`
	DescriptionRU string          `json:"description_ru"`
	DisplayAddress string         `json:"display_address"`
	GeocodingAddress string       `json:"geocoding_address"`
	Contact       string          `json:"contact"`
	Domain        string          `json:"domain"`
	UserCorrectedAddress int      `json:"user_corrected_address"`
	CreatedBy     string          `json:"created_by"`
	UpdatedBy     string          `json:"updated_by"`
	PropertyType  string          `json:"property_type"`
	Images        []ListingImage  `json:"images"`
	Features      []ListingFeature `json:"features"`
	Amenities     []ListingAmenity `json:"amenities"`
	Map           *ListingMap     `json:"map"`
	Latitude      float64         `json:"latitude,omitempty"`
	Longitude     float64         `json:"longitude,omitempty"`
}

type ListingData struct {
	URL              string                 `json:"url"`
	TitleRO          string                 `json:"title_ro"`
	TitleRU          string                 `json:"title_ru"`
	DescriptionRO    string                 `json:"description_ro"`
	DescriptionRU    string                 `json:"description_ru"`
	PriceJSON        string                 `json:"price_json"`
	Address          string                 `json:"address"`
	DisplayAddress   string                 `json:"display_address"`
	GeocodingAddress string                 `json:"geocoding_address"`
	Contact          string                 `json:"contact"`
	Domain           string                 `json:"domain"`
	Latitude         float64                `json:"latitude"`
	Longitude        float64                `json:"longitude"`
	MapTitle         string                 `json:"map_title"`
	Images           []ListingImageInput    `json:"images"`
	Features         []ListingFeatureInput  `json:"features"`
	Amenities        []ListingAmenityInput  `json:"amenities"`
	TemplateName     string                 `json:"template_name"`
	ListingType      string                 `json:"listing_type"`
	PropertyType     string                 `json:"property_type"`
	PriceEUR         string                 `json:"price_eur"`
	Status           string                 `json:"status"`
}

type ListingImageInput struct {
	ImageURL  string `json:"image_url"`
	LocalPath string `json:"local_path"`
	Position  int    `json:"position"`
}

type ListingFeatureInput struct {
	Lang         string `json:"lang"`
	Section      string `json:"section"`
	FeatureKey   string `json:"feature_key"`
	FeatureValue string `json:"feature_value"`
}

type ListingAmenityInput struct {
	Lang         string `json:"lang"`
	AmenityKey   string `json:"amenity_key"`
	AmenityValue string `json:"amenity_value"`
}

type SearchParams struct {
	Query        string   `json:"query"`
	PropertyType string   `json:"property_type"`
	ListingType  string   `json:"listing_type"`
	PriceMin     *float64 `json:"price_min"`
	PriceMax     *float64 `json:"price_max"`
	Status       string   `json:"status"`
	Section      string   `json:"section"`
	Tag          string   `json:"tag"`
	Limit        int      `json:"limit"`
	Offset       int      `json:"offset"`
}

type ListingStats struct {
	Total         int     `json:"total"`
	Active        int     `json:"active"`
	Sold          int     `json:"sold"`
	Rented        int     `json:"rented"`
	AvgPrice      float64 `json:"avg_price"`
	MedianPrice   float64 `json:"median_price"`
	MinPrice      float64 `json:"min_price"`
	MaxPrice      float64 `json:"max_price"`
	ByType        map[string]int `json:"by_type"`
	ByProperty    map[string]int `json:"by_property"`
}

type Coordinate struct {
	ID        string  `json:"id"`
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
	Title     string  `json:"title"`
	Status    string  `json:"status"`
}

// ─── Listings CRUD ─────────────────────────────────────────────────

// GetAllListings returns listings with optional status filter.
func GetAllListings(db *sql.DB, status string) ([]ListingBasic, error) {
	query := `SELECT id, url, title_ro, title_ru, price_json, address,
		folder_path, template_name, status, created_at, updated_at,
		listing_type, sold, rented
		FROM listings`
	var args []interface{}
	if status != "" && status != "all" {
		query += " WHERE status = ?"
		args = append(args, status)
	}
	query += " ORDER BY created_at DESC"

	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("get all listings: %w", err)
	}
	defer rows.Close()

	var listings []ListingBasic
	for rows.Next() {
		var l ListingBasic
		if err := rows.Scan(&l.ID, &l.URL, &l.TitleRO, &l.TitleRU,
			&l.PriceJSON, &l.Address, &l.FolderPath, &l.TemplateName,
			&l.Status, &l.CreatedAt, &l.UpdatedAt, &l.ListingType,
			&l.Sold, &l.Rented); err != nil {
			return nil, fmt.Errorf("scan listing: %w", err)
		}
		l.Price = parsePrice(l.PriceJSON)
		listings = append(listings, l)
	}
	return listings, nil
}

// GetListing returns full listing detail with images, features, amenities, map.
func GetListing(db *sql.DB, id string) (*ListingFull, error) {
	row := db.QueryRow(`SELECT id, url, domain, title_ro, title_ru,
		description_ro, description_ru, price_json, address, display_address,
		geocoding_address, contact, created_at, updated_at, folder_path,
		template_name, status, user_corrected_address, created_by, updated_by,
		sold, rented, listing_type, property_type
		FROM listings WHERE id = ?`, id)

	var l ListingFull
	err := row.Scan(&l.ID, &l.URL, &l.Domain, &l.TitleRO, &l.TitleRU,
		&l.DescriptionRO, &l.DescriptionRU, &l.PriceJSON, &l.Address,
		&l.DisplayAddress, &l.GeocodingAddress, &l.Contact,
		&l.CreatedAt, &l.UpdatedAt, &l.FolderPath, &l.TemplateName,
		&l.Status, &l.UserCorrectedAddress, &l.CreatedBy, &l.UpdatedBy,
		&l.Sold, &l.Rented, &l.ListingType, &l.PropertyType)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("get listing %s: %w", id, err)
	}

	// Load images
	l.Images = getListingImages(db, id)

	// Load features
	l.Features = getListingFeatures(db, id)

	// Load amenities
	l.Amenities = getListingAmenities(db, id)

	// Load map data
	l.Map = getListingMap(db, id)
	if l.Map != nil {
		l.Latitude = l.Map.Latitude
		l.Longitude = l.Map.Longitude
	}

	return &l, nil
}

// InsertListing creates a new listing with all related data in a transaction.
func InsertListing(db *sql.DB, data *ListingData) (string, error) {
	id := extractID(data.URL)
	now := time.Now().UTC().Format(time.RFC3339)

	tx, err := db.Begin()
	if err != nil {
		return "", fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	_, err = tx.Exec(`INSERT OR REPLACE INTO listings
		(id, url, domain, title_ro, title_ru, description_ro, description_ru,
		 price_json, address, display_address, geocoding_address, contact,
		 created_at, updated_at, template_name, status, listing_type, property_type)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		id, data.URL, data.Domain, data.TitleRO, data.TitleRU,
		data.DescriptionRO, data.DescriptionRU, data.PriceJSON,
		data.Address, data.DisplayAddress, data.GeocodingAddress, data.Contact,
		now, now, data.TemplateName, data.Status, data.ListingType, data.PropertyType)
	if err != nil {
		return "", fmt.Errorf("insert listing: %w", err)
	}

	// Insert map data if coordinates exist
	if data.Latitude != 0 || data.Longitude != 0 {
		_, err = tx.Exec(`INSERT OR REPLACE INTO listing_map
			(listing_id, latitude, longitude, map_title) VALUES (?, ?, ?, ?)`,
			id, data.Latitude, data.Longitude, data.MapTitle)
		if err != nil {
			return "", fmt.Errorf("insert map: %w", err)
		}
	}

	// Insert images
	for _, img := range data.Images {
		_, err = tx.Exec(`INSERT INTO listing_images
			(listing_id, image_url, local_path, position) VALUES (?, ?, ?, ?)`,
			id, img.ImageURL, img.LocalPath, img.Position)
		if err != nil {
			return "", fmt.Errorf("insert image: %w", err)
		}
	}

	// Insert features
	for _, f := range data.Features {
		_, err = tx.Exec(`INSERT INTO listing_features
			(listing_id, lang, section, feature_key, feature_value) VALUES (?, ?, ?, ?, ?)`,
			id, f.Lang, f.Section, f.FeatureKey, f.FeatureValue)
		if err != nil {
			return "", fmt.Errorf("insert feature: %w", err)
		}
	}

	// Insert amenities
	for _, a := range data.Amenities {
		_, err = tx.Exec(`INSERT INTO listing_amenities
			(listing_id, lang, amenity_key, amenity_value) VALUES (?, ?, ?, ?)`,
			id, a.Lang, a.AmenityKey, a.AmenityValue)
		if err != nil {
			return "", fmt.Errorf("insert amenity: %w", err)
		}
	}

	if err := tx.Commit(); err != nil {
		return "", fmt.Errorf("commit tx: %w", err)
	}
	return id, nil
}

// UpdateListing updates listing fields and optionally features/amenities.
func UpdateListing(db *sql.DB, id string, updates map[string]interface{}, user string) error {
	if len(updates) == 0 {
		return nil
	}

	now := time.Now().UTC().Format(time.RFC3339)
	updates["updated_at"] = now
	updates["updated_by"] = user

	var setClauses []string
	var args []interface{}
	for k, v := range updates {
		if k == "features" || k == "amenities" {
			continue
		}
		setClauses = append(setClauses, fmt.Sprintf("%s = ?", k))
		args = append(args, v)
	}
	args = append(args, id)

	query := fmt.Sprintf("UPDATE listings SET %s WHERE id = ?",
		joinStrings(setClauses, ", "))
	if _, err := db.Exec(query, args...); err != nil {
		return fmt.Errorf("update listing: %w", err)
	}

	// Update features if provided
	if features, ok := updates["features"]; ok {
		if err := replaceListingFeatures(db, id, features.([]ListingFeatureInput)); err != nil {
			return err
		}
	}

	// Update amenities if provided
	if amenities, ok := updates["amenities"]; ok {
		if err := replaceListingAmenities(db, id, amenities.([]ListingAmenityInput)); err != nil {
			return err
		}
	}

	return nil
}

// DeleteListing deletes a listing (cascades to all related tables).
func DeleteListing(db *sql.DB, id string) error {
	_, err := db.Exec("DELETE FROM listings WHERE id = ?", id)
	if err != nil {
		return fmt.Errorf("delete listing %s: %w", id, err)
	}
	return nil
}

// ToggleSold toggles the sold field.
func ToggleSold(db *sql.DB, id string) (string, error) {
	var current string
	err := db.QueryRow("SELECT sold FROM listings WHERE id = ?", id).Scan(&current)
	if err != nil {
		return "", fmt.Errorf("toggle sold: %w", err)
	}
	newVal := "yes"
	if current == "yes" {
		newVal = "no"
	}
	_, err = db.Exec("UPDATE listings SET sold = ?, updated_at = ? WHERE id = ?",
		newVal, time.Now().UTC().Format(time.RFC3339), id)
	if err != nil {
		return "", err
	}
	return newVal, nil
}

// ToggleRented toggles the rented field.
func ToggleRented(db *sql.DB, id string) (string, error) {
	var current string
	err := db.QueryRow("SELECT rented FROM listings WHERE id = ?", id).Scan(&current)
	if err != nil {
		return "", fmt.Errorf("toggle rented: %w", err)
	}
	newVal := "yes"
	if current == "yes" {
		newVal = "no"
	}
	_, err = db.Exec("UPDATE listings SET rented = ?, updated_at = ? WHERE id = ?",
		newVal, time.Now().UTC().Format(time.RFC3339), id)
	if err != nil {
		return "", err
	}
	return newVal, nil
}

// ─── Images ─────────────────────────────────────────────────────────

func getListingImages(db *sql.DB, listingID string) []ListingImage {
	rows, err := db.Query(
		"SELECT id, listing_id, image_url, local_path, position FROM listing_images WHERE listing_id = ? ORDER BY position",
		listingID)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var images []ListingImage
	for rows.Next() {
		var img ListingImage
		rows.Scan(&img.ID, &img.ListingID, &img.ImageURL, &img.LocalPath, &img.Position)
		images = append(images, img)
	}
	return images
}

// GetListingImages returns images for a listing.
func GetListingImages(db *sql.DB, listingID string) ([]ListingImage, error) {
	rows, err := db.Query(
		"SELECT id, listing_id, image_url, local_path, position FROM listing_images WHERE listing_id = ? ORDER BY position",
		listingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var images []ListingImage
	for rows.Next() {
		var img ListingImage
		rows.Scan(&img.ID, &img.ListingID, &img.ImageURL, &img.LocalPath, &img.Position)
		images = append(images, img)
	}
	return images, nil
}

// ─── Features ───────────────────────────────────────────────────────

func getListingFeatures(db *sql.DB, listingID string) []ListingFeature {
	rows, err := db.Query(
		"SELECT id, listing_id, lang, section, feature_key, feature_value FROM listing_features WHERE listing_id = ?",
		listingID)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var features []ListingFeature
	for rows.Next() {
		var f ListingFeature
		rows.Scan(&f.ID, &f.ListingID, &f.Lang, &f.Section, &f.FeatureKey, &f.FeatureValue)
		features = append(features, f)
	}
	return features
}

func replaceListingFeatures(db *sql.DB, listingID string, features []ListingFeatureInput) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	tx.Exec("DELETE FROM listing_features WHERE listing_id = ?", listingID)
	for _, f := range features {
		_, err = tx.Exec(`INSERT INTO listing_features
			(listing_id, lang, section, feature_key, feature_value) VALUES (?, ?, ?, ?, ?)`,
			listingID, f.Lang, f.Section, f.FeatureKey, f.FeatureValue)
		if err != nil {
			return fmt.Errorf("insert feature: %w", err)
		}
	}
	return tx.Commit()
}

// ─── Amenities ──────────────────────────────────────────────────────

func getListingAmenities(db *sql.DB, listingID string) []ListingAmenity {
	rows, err := db.Query(
		"SELECT id, listing_id, lang, amenity_key, amenity_value FROM listing_amenities WHERE listing_id = ?",
		listingID)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var amenities []ListingAmenity
	for rows.Next() {
		var a ListingAmenity
		rows.Scan(&a.ID, &a.ListingID, &a.Lang, &a.AmenityKey, &a.AmenityValue)
		amenities = append(amenities, a)
	}
	return amenities
}

func replaceListingAmenities(db *sql.DB, listingID string, amenities []ListingAmenityInput) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	tx.Exec("DELETE FROM listing_amenities WHERE listing_id = ?", listingID)
	for _, a := range amenities {
		_, err = tx.Exec(`INSERT INTO listing_amenities
			(listing_id, lang, amenity_key, amenity_value) VALUES (?, ?, ?, ?)`,
			listingID, a.Lang, a.AmenityKey, a.AmenityValue)
		if err != nil {
			return fmt.Errorf("insert amenity: %w", err)
		}
	}
	return tx.Commit()
}

// ─── Map ────────────────────────────────────────────────────────────

func getListingMap(db *sql.DB, listingID string) *ListingMap {
	row := db.QueryRow("SELECT listing_id, latitude, longitude, map_title FROM listing_map WHERE listing_id = ?", listingID)
	var m ListingMap
	if err := row.Scan(&m.ListingID, &m.Latitude, &m.Longitude, &m.MapTitle); err != nil {
		return nil
	}
	return &m
}

// ─── POI ────────────────────────────────────────────────────────────

// SavePOIData saves POI data for a listing category.
func SavePOIData(db *sql.DB, listingID string, poiData map[string][]interface{}, radius int) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	tx.Exec("DELETE FROM listing_pois WHERE listing_id = ?", listingID)
	for category, pois := range poiData {
		data, _ := json.Marshal(pois)
		_, err = tx.Exec(`INSERT INTO listing_pois (listing_id, category, poi_data, radius) VALUES (?, ?, ?, ?)`,
			listingID, category, string(data), radius)
		if err != nil {
			return fmt.Errorf("insert poi: %w", err)
		}
	}
	return tx.Commit()
}

// GetPOIData returns POI data for a listing.
func GetPOIData(db *sql.DB, listingID string) ([]ListingPOI, error) {
	rows, err := db.Query(
		"SELECT id, listing_id, category, poi_data, generated_at, radius FROM listing_pois WHERE listing_id = ? ORDER BY category",
		listingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var pois []ListingPOI
	for rows.Next() {
		var p ListingPOI
		rows.Scan(&p.ID, &p.ListingID, &p.Category, &p.POIData, &p.GeneratedAt, &p.Radius)
		pois = append(pois, p)
	}
	return pois, nil
}

// ─── Search ─────────────────────────────────────────────────────────

// ExpressSearch performs filtered search across listings.
func ExpressSearch(db *sql.DB, p SearchParams) ([]ListingBasic, int, error) {
	where := []string{"1=1"}
	var args []interface{}

	if p.Query != "" {
		where = append(where, "(title_ro LIKE ? OR title_ru LIKE ? OR address LIKE ? OR contact LIKE ?)")
		q := "%" + p.Query + "%"
		args = append(args, q, q, q, q)
	}
	if p.PropertyType != "" {
		where = append(where, "property_type = ?")
		args = append(args, p.PropertyType)
	}
	if p.ListingType != "" {
		where = append(where, "listing_type = ?")
		args = append(args, p.ListingType)
	}
	if p.Status != "" && p.Status != "all" {
		where = append(where, "status = ?")
		args = append(args, p.Status)
	}
	if p.Section != "" {
		where = append(where, "id IN (SELECT DISTINCT listing_id FROM listing_features WHERE section = ?)")
		args = append(args, p.Section)
	}

	// Count total
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM listings WHERE %s", joinStrings(where, " AND "))
	var total int
	db.QueryRow(countQuery, args...).Scan(&total)

	// Fetch results
	limit := p.Limit
	if limit <= 0 {
		limit = 50
	}
	offset := p.Offset

	query := fmt.Sprintf(`SELECT id, url, title_ro, title_ru, price_json, address,
		folder_path, template_name, status, created_at, updated_at,
		listing_type, sold, rented FROM listings WHERE %s ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		joinStrings(where, " AND "))
	args = append(args, limit, offset)

	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("search: %w", err)
	}
	defer rows.Close()

	var listings []ListingBasic
	for rows.Next() {
		var l ListingBasic
		rows.Scan(&l.ID, &l.URL, &l.TitleRO, &l.TitleRU,
			&l.PriceJSON, &l.Address, &l.FolderPath, &l.TemplateName,
			&l.Status, &l.CreatedAt, &l.UpdatedAt, &l.ListingType,
			&l.Sold, &l.Rented)
		l.Price = parsePrice(l.PriceJSON)
		listings = append(listings, l)
	}
	return listings, total, nil
}

// ─── Coordinates ────────────────────────────────────────────────────

// GetCoordinates returns all listings with map coordinates.
func GetCoordinates(db *sql.DB) ([]Coordinate, error) {
	rows, err := db.Query(`SELECT l.id, m.latitude, m.longitude, l.title_ro, l.status
		FROM listings l INNER JOIN listing_map m ON l.id = m.listing_id
		WHERE m.latitude IS NOT NULL AND m.longitude IS NOT NULL`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var coords []Coordinate
	for rows.Next() {
		var c Coordinate
		rows.Scan(&c.ID, &c.Latitude, &c.Longitude, &c.Title, &c.Status)
		coords = append(coords, c)
	}
	return coords, nil
}

// ─── Statistics ─────────────────────────────────────────────────────

// GetStatistics returns aggregated listing statistics.
func GetStatistics(db *sql.DB) (*ListingStats, error) {
	var s ListingStats
	s.ByType = make(map[string]int)
	s.ByProperty = make(map[string]int)

	db.QueryRow("SELECT COUNT(*) FROM listings").Scan(&s.Total)
	db.QueryRow("SELECT COUNT(*) FROM listings WHERE status = 'active'").Scan(&s.Active)
	db.QueryRow("SELECT COUNT(*) FROM listings WHERE sold = 'yes'").Scan(&s.Sold)
	db.QueryRow("SELECT COUNT(*) FROM listings WHERE rented = 'yes'").Scan(&s.Rented)
	db.QueryRow("SELECT COALESCE(AVG(CAST(price_json AS REAL)), 0) FROM listings WHERE price_json != '{}' AND price_json != ''").Scan(&s.AvgPrice)

	// Price extremes
	db.QueryRow("SELECT COALESCE(MIN(CAST(price_json AS REAL)), 0) FROM listings WHERE price_json != '{}' AND price_json != ''").Scan(&s.MinPrice)
	db.QueryRow("SELECT COALESCE(MAX(CAST(price_json AS REAL)), 0) FROM listings WHERE price_json != '{}' AND price_json != ''").Scan(&s.MaxPrice)

	// By listing type
	rows, _ := db.Query("SELECT listing_type, COUNT(*) FROM listings GROUP BY listing_type")
	if rows != nil {
		defer rows.Close()
		for rows.Next() {
			var k string
			var v int
			rows.Scan(&k, &v)
			s.ByType[k] = v
		}
	}

	// By property type
	rows2, _ := db.Query("SELECT property_type, COUNT(*) FROM listings GROUP BY property_type")
	if rows2 != nil {
		defer rows2.Close()
		for rows2.Next() {
			var k string
			var v int
			rows2.Scan(&k, &v)
			s.ByProperty[k] = v
		}
	}

	return &s, nil
}

// ─── Templates ──────────────────────────────────────────────────────

type TemplateInfo struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}

// GetTemplates returns available listing templates.
func GetTemplates() []TemplateInfo {
	return []TemplateInfo{
		{Name: "luna", Description: "Modern clean design with sidebar"},
		{Name: "thunder", Description: "Bold editorial layout"},
	}
}

// ─── Helpers ───────────────────────────────────────────────────────

func joinStrings(elems []string, sep string) string {
	if len(elems) == 0 {
		return ""
	}
	result := elems[0]
	for _, e := range elems[1:] {
		result += sep + e
	}
	return result
}

// extractID extracts the listing ID from a 999.md URL.
func extractID(url string) string {
	// URLs like https://999.md/ro/123456789
	id := url
	for len(id) > 0 && id[len(id)-1] == '/' {
		id = id[:len(id)-1]
	}
	for i := len(id) - 1; i >= 0; i-- {
		if id[i] == '/' {
			return id[i+1:]
		}
	}
	return id
}
