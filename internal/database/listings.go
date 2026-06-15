package database

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"sort"
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
	PropertyType string `json:"property_type"`
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
	TotalListings            int                `json:"total_listings"`
	ForSaleAvailable         int                `json:"for_sale_available"`
	ForSaleSold              int                `json:"for_sale_sold"`
	ForRentAvailable         int                `json:"for_rent_available"`
	ForRentRented            int                `json:"for_rent_rented"`
	TotalValue               float64            `json:"total_value"`
	AveragePrice             float64            `json:"average_price"`
	MinPrice                 float64            `json:"min_price"`
	MaxPrice                 float64            `json:"max_price"`
	SaleAvgPrice             float64            `json:"sale_avg_price"`
	SaleMinPrice             float64            `json:"sale_min_price"`
	SaleMaxPrice             float64            `json:"sale_max_price"`
	RentAvgPrice             float64            `json:"rent_avg_price"`
	RentMinPrice             float64            `json:"rent_min_price"`
	RentMaxPrice             float64            `json:"rent_max_price"`
	Currency                 string             `json:"currency"`
	CurrenciesBreakdown      map[string]int     `json:"currencies_breakdown"`
	TotalImages              int                `json:"total_images"`
	AvgImagesPerListing      float64            `json:"avg_images_per_listing"`
	OldestListingDate        string             `json:"oldest_listing_date"`
	NewestListingDate        string             `json:"newest_listing_date"`
	RecentListings           []RecentListing    `json:"recent_listings"`
	Locations                []LocationStat     `json:"locations"`
	PropertyTypesSale        map[string]int     `json:"property_types_sale"`
	PropertyTypesRent        map[string]int     `json:"property_types_rent"`
	RoomsSale                map[string]int     `json:"rooms_sale"`
	RoomsRent                map[string]int     `json:"rooms_rent"`
	AvgSurfaceSale           float64            `json:"avg_surface_sale"`
	AvgSurfaceRent           float64            `json:"avg_surface_rent"`
	AvgSurfaceSaleHouse      float64            `json:"avg_surface_sale_house"`
	AvgSurfaceSaleApartment  float64            `json:"avg_surface_sale_apartment"`
	AvgSurfaceSaleCommercial float64            `json:"avg_surface_sale_commercial"`
	AvgSurfaceRentHouse      float64            `json:"avg_surface_rent_house"`
	AvgSurfaceRentApartment  float64            `json:"avg_surface_rent_apartment"`
	AvgSurfaceRentCommercial float64            `json:"avg_surface_rent_commercial"`
	AvgPricePerSqmSale       float64            `json:"avg_price_per_sqm_sale"`
	AvgPricePerSqmRent       float64            `json:"avg_price_per_sqm_rent"`
	AvgPricePerSqmSaleHouse      float64        `json:"avg_price_per_sqm_sale_house"`
	AvgPricePerSqmSaleApartment  float64        `json:"avg_price_per_sqm_sale_apartment"`
	AvgPricePerSqmSaleCommercial float64        `json:"avg_price_per_sqm_sale_commercial"`
	AvgPricePerSqmRentHouse      float64        `json:"avg_price_per_sqm_rent_house"`
	AvgPricePerSqmRentApartment  float64        `json:"avg_price_per_sqm_rent_apartment"`
	AvgPricePerSqmRentCommercial float64        `json:"avg_price_per_sqm_rent_commercial"`
	SalePercentiles          map[string]float64 `json:"sale_percentiles"`
	RentPercentiles          map[string]float64 `json:"rent_percentiles"`
	TopAmenitiesSale         []AmenityCount     `json:"top_amenities_sale"`
	TopAmenitiesRent         []AmenityCount     `json:"top_amenities_rent"`
}

type RecentListing struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Date  string `json:"date"`
}

type LocationStat struct {
	Name  string `json:"name"`
	Count int    `json:"count"`
}

type AmenityCount struct {
	Name  string `json:"name"`
	Count int    `json:"count"`
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
		COALESCE(folder_path,'') as folder_path, template_name, status, created_at, updated_at,
		listing_type, property_type, sold, rented
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
			&l.PropertyType, &l.Sold, &l.Rented); err != nil {
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
		geocoding_address, contact, created_at, updated_at, COALESCE(folder_path,'') as folder_path,
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
	if featuresRaw, ok := updates["features"]; ok {
		data, _ := json.Marshal(featuresRaw)
		var features []ListingFeatureInput
		if err := json.Unmarshal(data, &features); err != nil {
			return fmt.Errorf("unmarshal features: %w", err)
		}
		if err := replaceListingFeatures(db, id, features); err != nil {
			return err
		}
	}

	// Update amenities if provided
	if amenitiesRaw, ok := updates["amenities"]; ok {
		data, _ := json.Marshal(amenitiesRaw)
		var amenities []ListingAmenityInput
		if err := json.Unmarshal(data, &amenities); err != nil {
			return fmt.Errorf("unmarshal amenities: %w", err)
		}
		if err := replaceListingAmenities(db, id, amenities); err != nil {
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

// GetFirstImages returns a map of listing_id → first image local_path.
func GetFirstImages(db *sql.DB) map[string]string {
	result := make(map[string]string)
	rows, err := db.Query(
		`SELECT listing_id, local_path FROM listing_images
		 WHERE (listing_id, position) IN (
		   SELECT listing_id, MIN(position) FROM listing_images GROUP BY listing_id
		 )`)
	if err != nil {
		return result
	}
	defer rows.Close()
	for rows.Next() {
		var id, path string
		rows.Scan(&id, &path)
		result[id] = path
	}
	return result
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
		COALESCE(folder_path,'') as folder_path, template_name, status, created_at, updated_at,
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

// GetStatistics returns comprehensive listing statistics matching the Flask implementation.
func GetStatistics(db *sql.DB) (*ListingStats, error) {
	s := &ListingStats{}
	s.CurrenciesBreakdown = make(map[string]int)
	s.PropertyTypesSale = make(map[string]int)
	s.PropertyTypesRent = make(map[string]int)
	s.RoomsSale = make(map[string]int)
	s.RoomsRent = make(map[string]int)

	// Step 1: Total active listings
	if err := db.QueryRow("SELECT COUNT(*) FROM listings WHERE status = 'active'").Scan(&s.TotalListings); err != nil {
		return nil, fmt.Errorf("count listings: %w", err)
	}

	// Step 2: Count by listing_type, sold, rented
	{
		rows, err := db.Query(`
			SELECT listing_type, sold, rented, COUNT(*) as count
			FROM listings WHERE status = 'active'
			GROUP BY listing_type, sold, rented
		`)
		if err != nil {
			return nil, fmt.Errorf("type breakdown: %w", err)
		}
		for rows.Next() {
			var listingType, sold, rented string
			var count int
			if err := rows.Scan(&listingType, &sold, &rented, &count); err != nil {
				rows.Close()
				return nil, fmt.Errorf("scan type row: %w", err)
			}
			switch listingType {
			case "for_sale":
				if sold == "yes" {
					s.ForSaleSold += count
				} else {
					s.ForSaleAvailable += count
				}
			case "for_rent":
				if rented == "yes" {
					s.ForRentRented += count
				} else {
					s.ForRentAvailable += count
				}
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}

	// Step 3: Features + listings data for rooms, surface, property_type
	type listingData struct {
		listingType  string
		propertyType string
		features     map[string]string
	}
	listingFeaturesMap := make(map[string]*listingData)

	{
		rows, err := db.Query(`
			SELECT l.id, l.listing_type, l.property_type, f.feature_key, f.feature_value
			FROM listings l
			LEFT JOIN listing_features f ON l.id = f.listing_id
			WHERE l.status = 'active'
		`)
		if err != nil {
			return nil, fmt.Errorf("features query: %w", err)
		}
		for rows.Next() {
			var id, listingType string
			var propertyType, featureKey, featureValue sql.NullString
			if err := rows.Scan(&id, &listingType, &propertyType, &featureKey, &featureValue); err != nil {
				rows.Close()
				return nil, fmt.Errorf("scan features row: %w", err)
			}
			ld, ok := listingFeaturesMap[id]
			if !ok {
				propType := "apartment"
				if propertyType.Valid && propertyType.String != "" {
					propType = propertyType.String
				}
				ld = &listingData{
					listingType:  listingType,
					propertyType: propType,
					features:     make(map[string]string),
				}
				listingFeaturesMap[id] = ld
			}
			if featureKey.Valid && featureValue.Valid {
				ld.features[strings.ToLower(featureKey.String)] = strings.ToLower(featureValue.String)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}

	// Step 4: Prices
	type priceEntry struct {
		price       float64
		listingType string
	}
	var prices, salePrices, rentPrices []float64
	var totalValue float64
	currencies := make(map[string]int)
	salePricesByType := map[string][]float64{"house": {}, "apartment": {}, "commercial": {}}
	rentPricesByType := map[string][]float64{"house": {}, "apartment": {}, "commercial": {}}
	priceByListing := make(map[string][]priceEntry)

	{
		rows, err := db.Query(`
			SELECT id, price_json, listing_type, sold, rented
			FROM listings WHERE status = 'active'
		`)
		if err != nil {
			return nil, fmt.Errorf("price query: %w", err)
		}
		for rows.Next() {
			var id, listingType, sold, rented string
			var priceJSON sql.NullString
			if err := rows.Scan(&id, &priceJSON, &listingType, &sold, &rented); err != nil {
				rows.Close()
				return nil, fmt.Errorf("scan price row: %w", err)
			}
			if !priceJSON.Valid || priceJSON.String == "" || priceJSON.String == "{}" {
				continue
			}
			var priceObj map[string]string
			if err := json.Unmarshal([]byte(priceJSON.String), &priceObj); err != nil {
				continue
			}
			if listingType == "" {
				listingType = "for_sale"
			}

			ld, hasLD := listingFeaturesMap[id]
			propertyType := "apartment"
			if hasLD {
				propertyType = ld.propertyType
			}
			pTypes := []string{propertyType}
			if _, ok := map[string]bool{"house": true, "apartment": true, "commercial": true}[propertyType]; !ok {
				pTypes = []string{"house", "apartment", "commercial"}
			}

			for currency, priceStr := range priceObj {
				numericPrice := extractNumericPrice(priceStr)
				if numericPrice <= 0 {
					continue
				}
				prices = append(prices, numericPrice)
				totalValue += numericPrice
				currencies[currency]++

				pe := priceEntry{price: numericPrice, listingType: listingType}
				priceByListing[id] = append(priceByListing[id], pe)

				if listingType == "for_sale" {
					salePrices = append(salePrices, numericPrice)
					for _, pt := range pTypes {
						salePricesByType[pt] = append(salePricesByType[pt], numericPrice)
					}
				} else if listingType == "for_rent" {
					rentPrices = append(rentPrices, numericPrice)
					for _, pt := range pTypes {
						rentPricesByType[pt] = append(rentPricesByType[pt], numericPrice)
					}
				}
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
		s.TotalValue = round2(totalValue)
	}

	// Step 5: Price stats
	if len(prices) > 0 {
		sort.Float64s(prices)
		var sum float64
		for _, p := range prices {
			sum += p
		}
		s.AveragePrice = round2(sum / float64(len(prices)))
		s.MinPrice = round2(prices[0])
		s.MaxPrice = round2(prices[len(prices)-1])
	}
	if len(salePrices) > 0 {
		sort.Float64s(salePrices)
		var sum float64
		for _, p := range salePrices {
			sum += p
		}
		s.SaleAvgPrice = round2(sum / float64(len(salePrices)))
		s.SaleMinPrice = round2(salePrices[0])
		s.SaleMaxPrice = round2(salePrices[len(salePrices)-1])
	}
	if len(rentPrices) > 0 {
		sort.Float64s(rentPrices)
		var sum float64
		for _, p := range rentPrices {
			sum += p
		}
		s.RentAvgPrice = round2(sum / float64(len(rentPrices)))
		s.RentMinPrice = round2(rentPrices[0])
		s.RentMaxPrice = round2(rentPrices[len(rentPrices)-1])
	}

	// Most common currency
	s.Currency = "EUR"
	maxCount := 0
	for curr, count := range currencies {
		s.CurrenciesBreakdown[curr] = count
		if count > maxCount {
			maxCount = count
			s.Currency = curr
		}
	}
	if len(currencies) == 0 {
		s.Currency = "EUR"
	}

	// Step 6: Property types from listings table
	{
		rows, err := db.Query(`
			SELECT listing_type, property_type
			FROM listings WHERE status = 'active'
		`)
		if err != nil {
			return nil, fmt.Errorf("property types query: %w", err)
		}
		for rows.Next() {
			var listingType string
			var propertyType sql.NullString
			if err := rows.Scan(&listingType, &propertyType); err != nil {
				rows.Close()
				return nil, fmt.Errorf("scan property type: %w", err)
			}
			propType := "apartment"
			if propertyType.Valid && propertyType.String != "" {
				propType = propertyType.String
			}
			switch listingType {
			case "for_sale":
				s.PropertyTypesSale[propType]++
			case "for_rent":
				s.PropertyTypesRent[propType]++
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}

	// Step 7+8: Rooms and Surface from features
	surfaceAreasSale := map[string][]float64{"house": {}, "apartment": {}, "commercial": {}}
	surfaceAreasRent := map[string][]float64{"house": {}, "apartment": {}, "commercial": {}}

	for _, ld := range listingFeaturesMap {
		// Rooms
		rooms := 0
		for _, key := range []string{"număr de camere", "camere", "nr. camere"} {
			if v, ok := ld.features[key]; ok {
				parts := strings.Fields(v)
				if len(parts) > 0 {
					if r, err := strconv.Atoi(parts[0]); err == nil && r > 0 {
						rooms = r
						break
					}
				}
			}
		}
		if rooms > 0 {
			k := strconv.Itoa(rooms)
			switch ld.listingType {
			case "for_sale":
				s.RoomsSale[k]++
			case "for_rent":
				s.RoomsRent[k]++
			}
		}

		// Surface area
		var surface float64
		for _, key := range []string{"suprafața totală", "suprafață locativă", "общая площадь", "жилая площадь"} {
			if v, ok := ld.features[key]; ok {
				cleaned := strings.ReplaceAll(strings.ReplaceAll(v, "m²", ""), "m2", "")
				cleaned = strings.TrimSpace(cleaned)
				parts := strings.Fields(cleaned)
				if len(parts) > 0 {
					if sf, err := strconv.ParseFloat(parts[0], 64); err == nil && sf > 0 {
						surface = sf
						break
					}
				}
			}
		}
		if surface > 0 {
			propType := ld.propertyType
			if _, ok := map[string]bool{"house": true, "apartment": true, "commercial": true}[propType]; !ok {
				propType = "apartment"
			}
			switch ld.listingType {
			case "for_sale":
				surfaceAreasSale[propType] = append(surfaceAreasSale[propType], surface)
			case "for_rent":
				surfaceAreasRent[propType] = append(surfaceAreasRent[propType], surface)
			}
		}
	}

	// Step 9: Price per sqm
	salePricePerSqm := map[string][]float64{"house": {}, "apartment": {}, "commercial": {}}
	rentPricePerSqm := map[string][]float64{"house": {}, "apartment": {}, "commercial": {}}

	for id, ld := range listingFeaturesMap {
		entries, ok := priceByListing[id]
		if !ok {
			continue
		}
		var surface float64
		for _, key := range []string{"suprafața totală", "suprafață locativă", "общая площадь", "жилая площадь"} {
			if v, ok2 := ld.features[key]; ok2 {
				cleaned := strings.ReplaceAll(strings.ReplaceAll(v, "m²", ""), "m2", "")
				cleaned = strings.TrimSpace(cleaned)
				parts := strings.Fields(cleaned)
				if len(parts) > 0 {
					if sf, err := strconv.ParseFloat(parts[0], 64); err == nil && sf > 0 {
						surface = sf
						break
					}
				}
			}
		}
		if surface <= 0 {
			continue
		}
		propType := ld.propertyType
		if _, valid := map[string]bool{"house": true, "apartment": true, "commercial": true}[propType]; !valid {
			propType = "apartment"
		}
		for _, entry := range entries {
			pricePerSqm := entry.price / surface
			switch entry.listingType {
			case "for_sale":
				salePricePerSqm[propType] = append(salePricePerSqm[propType], pricePerSqm)
			case "for_rent":
				rentPricePerSqm[propType] = append(rentPricePerSqm[propType], pricePerSqm)
			}
		}
	}

	// Step 10: Surface area statistics
	allSaleSurfaces := append(append(surfaceAreasSale["apartment"], surfaceAreasSale["house"]...), surfaceAreasSale["commercial"]...)
	allRentSurfaces := append(append(surfaceAreasRent["apartment"], surfaceAreasRent["house"]...), surfaceAreasRent["commercial"]...)

	if len(allSaleSurfaces) > 0 {
		var sum float64
		for _, v := range allSaleSurfaces {
			sum += v
		}
		s.AvgSurfaceSale = round1(sum / float64(len(allSaleSurfaces)))
	}
	if len(allRentSurfaces) > 0 {
		var sum float64
		for _, v := range allRentSurfaces {
			sum += v
		}
		s.AvgSurfaceRent = round1(sum / float64(len(allRentSurfaces)))
	}
	if len(surfaceAreasSale["house"]) > 0 {
		var sum float64
		for _, v := range surfaceAreasSale["house"] {
			sum += v
		}
		s.AvgSurfaceSaleHouse = round1(sum / float64(len(surfaceAreasSale["house"])))
	}
	if len(surfaceAreasSale["apartment"]) > 0 {
		var sum float64
		for _, v := range surfaceAreasSale["apartment"] {
			sum += v
		}
		s.AvgSurfaceSaleApartment = round1(sum / float64(len(surfaceAreasSale["apartment"])))
	}
	if len(surfaceAreasSale["commercial"]) > 0 {
		var sum float64
		for _, v := range surfaceAreasSale["commercial"] {
			sum += v
		}
		s.AvgSurfaceSaleCommercial = round1(sum / float64(len(surfaceAreasSale["commercial"])))
	}
	if len(surfaceAreasRent["house"]) > 0 {
		var sum float64
		for _, v := range surfaceAreasRent["house"] {
			sum += v
		}
		s.AvgSurfaceRentHouse = round1(sum / float64(len(surfaceAreasRent["house"])))
	}
	if len(surfaceAreasRent["apartment"]) > 0 {
		var sum float64
		for _, v := range surfaceAreasRent["apartment"] {
			sum += v
		}
		s.AvgSurfaceRentApartment = round1(sum / float64(len(surfaceAreasRent["apartment"])))
	}
	if len(surfaceAreasRent["commercial"]) > 0 {
		var sum float64
		for _, v := range surfaceAreasRent["commercial"] {
			sum += v
		}
		s.AvgSurfaceRentCommercial = round1(sum / float64(len(surfaceAreasRent["commercial"])))
	}

	// Step 11: Price per sqm stats (overall uses sum(all prices) / len(all surfaces) like Flask)
	if len(allSaleSurfaces) > 0 {
		var sumSale float64
		for _, p := range salePrices {
			sumSale += p
		}
		s.AvgPricePerSqmSale = round2(sumSale / float64(len(allSaleSurfaces)))
	}
	if len(allRentSurfaces) > 0 {
		var sumRent float64
		for _, p := range rentPrices {
			sumRent += p
		}
		s.AvgPricePerSqmRent = round2(sumRent / float64(len(allRentSurfaces)))
	}
	if len(salePricePerSqm["house"]) > 0 {
		var sum float64
		for _, v := range salePricePerSqm["house"] {
			sum += v
		}
		s.AvgPricePerSqmSaleHouse = round2(sum / float64(len(salePricePerSqm["house"])))
	}
	if len(salePricePerSqm["apartment"]) > 0 {
		var sum float64
		for _, v := range salePricePerSqm["apartment"] {
			sum += v
		}
		s.AvgPricePerSqmSaleApartment = round2(sum / float64(len(salePricePerSqm["apartment"])))
	}
	if len(salePricePerSqm["commercial"]) > 0 {
		var sum float64
		for _, v := range salePricePerSqm["commercial"] {
			sum += v
		}
		s.AvgPricePerSqmSaleCommercial = round2(sum / float64(len(salePricePerSqm["commercial"])))
	}
	if len(rentPricePerSqm["house"]) > 0 {
		var sum float64
		for _, v := range rentPricePerSqm["house"] {
			sum += v
		}
		s.AvgPricePerSqmRentHouse = round2(sum / float64(len(rentPricePerSqm["house"])))
	}
	if len(rentPricePerSqm["apartment"]) > 0 {
		var sum float64
		for _, v := range rentPricePerSqm["apartment"] {
			sum += v
		}
		s.AvgPricePerSqmRentApartment = round2(sum / float64(len(rentPricePerSqm["apartment"])))
	}
	if len(rentPricePerSqm["commercial"]) > 0 {
		var sum float64
		for _, v := range rentPricePerSqm["commercial"] {
			sum += v
		}
		s.AvgPricePerSqmRentCommercial = round2(sum / float64(len(rentPricePerSqm["commercial"])))
	}

	// Step 12: Price percentiles
	s.SalePercentiles = calculatePercentiles(salePrices)
	s.RentPercentiles = calculatePercentiles(rentPrices)

	// Step 13: Image stats
	if err := db.QueryRow(`
		SELECT COUNT(*) FROM listing_images li
		JOIN listings l ON li.listing_id = l.id
		WHERE l.status = 'active'
	`).Scan(&s.TotalImages); err != nil {
		// if table doesn't exist, images are 0
		s.TotalImages = 0
	}
	if s.TotalListings > 0 {
		s.AvgImagesPerListing = round1(float64(s.TotalImages) / float64(s.TotalListings))
	}

	// Step 14: Date range
	{
		var oldest, newest sql.NullString
		if err := db.QueryRow(`
			SELECT MIN(created_at), MAX(created_at)
			FROM listings WHERE status = 'active'
		`).Scan(&oldest, &newest); err == nil {
			if oldest.Valid {
				s.OldestListingDate = oldest.String
			}
			if newest.Valid {
				s.NewestListingDate = newest.String
			}
		}
	}

	// Step 15: Recent listings
	{
		rows, err := db.Query(`
			SELECT id, title_ro, created_at
			FROM listings WHERE status = 'active'
			ORDER BY created_at DESC LIMIT 7
		`)
		if err == nil {
			for rows.Next() {
				var id, createdAt string
				var title sql.NullString
				if err := rows.Scan(&id, &title, &createdAt); err == nil {
					titleStr := ""
					if title.Valid {
						titleStr = title.String
					}
					if len(titleStr) > 50 {
						titleStr = titleStr[:50] + "..."
					}
					s.RecentListings = append(s.RecentListings, RecentListing{
						ID: id, Title: titleStr, Date: createdAt,
					})
				}
			}
			rows.Close()
		}
	}

	// Step 16: Amenities
	{
		rows, err := db.Query(`
			SELECT l.listing_type, la.amenity_key
			FROM listing_amenities la
			JOIN listings l ON la.listing_id = l.id
			WHERE l.status = 'active' AND la.lang = 'ro'
		`)
		if err == nil {
			amenitiesSale := make(map[string]int)
			amenitiesRent := make(map[string]int)
			for rows.Next() {
				var listingType, amenityKey string
				if err := rows.Scan(&listingType, &amenityKey); err == nil {
					if listingType == "" {
						listingType = "for_sale"
					}
					switch listingType {
					case "for_sale":
						amenitiesSale[amenityKey]++
					case "for_rent":
						amenitiesRent[amenityKey]++
					}
				}
			}
			rows.Close()
			s.TopAmenitiesSale = topNAmenities(amenitiesSale, 10)
			s.TopAmenitiesRent = topNAmenities(amenitiesRent, 10)
		}
	}

	// Step 17: Location stats
	{
		rows, err := db.Query(`
			SELECT id, address FROM listings
			WHERE status = 'active' AND address IS NOT NULL AND address != ''
		`)
		if err == nil {
			locationCounts := make(map[string]int)
			for rows.Next() {
				var id, address string
				if err := rows.Scan(&id, &address); err != nil {
					continue
				}
				parts := strings.Split(address, ",")
				for i := range parts {
					parts[i] = strings.TrimSpace(parts[i])
				}
				city := ""
				district := ""
				street := ""
				if len(parts) >= 2 {
					if strings.Contains(parts[0], "mun.") {
						city = strings.TrimSpace(strings.Replace(parts[0], "mun.", "", 1))
					} else if len(parts) > 1 {
						city = strings.TrimSpace(parts[1])
					}
					for _, p := range parts {
						lower := strings.ToLower(p)
						if strings.Contains(lower, "raion") || strings.Contains(lower, "sector") {
							district = strings.TrimSpace(p)
							break
						}
					}
					for _, p := range parts {
						lower := strings.ToLower(p)
						if strings.Contains(lower, "str.") || strings.Contains(lower, "strada") ||
							strings.Contains(lower, "bd.") || strings.Contains(lower, "bulevardul") {
							street = strings.TrimSpace(p)
							break
						}
					}
				}
				if city != "" || district != "" || street != "" {
					var locParts []string
					if city != "" {
						locParts = append(locParts, city)
					}
					if district != "" {
						locParts = append(locParts, district)
					}
					if street != "" {
						locParts = append(locParts, street)
					}
					label := strings.Join(locParts, ", ")
					locationCounts[label]++
				}
			}
			rows.Close()
			s.Locations = topNLocations(locationCounts, 10)
		}
	}

	return s, nil
}

// extractNumericPrice removes currency formatting and returns the numeric value.
func extractNumericPrice(s string) float64 {
	re := regexp.MustCompile(`[^0-9.]`)
	cleaned := re.ReplaceAllString(strings.ReplaceAll(strings.ReplaceAll(s, ",", ""), " ", ""), "")
	val, _ := strconv.ParseFloat(cleaned, 64)
	return val
}

// calculatePercentiles computes p25, p50, p75, p90 from a sorted copy of prices.
func calculatePercentiles(prices []float64) map[string]float64 {
	if len(prices) == 0 {
		return map[string]float64{"p25": 0, "p50": 0, "p75": 0, "p90": 0}
	}
	sorted := make([]float64, len(prices))
	copy(sorted, prices)
	sort.Float64s(sorted)
	n := len(sorted)
	return map[string]float64{
		"p25": round2(sorted[int(float64(n)*0.25)]),
		"p50": round2(sorted[int(float64(n)*0.50)]),
		"p75": round2(sorted[int(float64(n)*0.75)]),
		"p90": round2(sorted[int(float64(n)*0.90)]),
	}
}

// round2 rounds a float64 to 2 decimal places.
func round2(v float64) float64 {
	return math.Round(v*100) / 100
}

// round1 rounds a float64 to 1 decimal place.
func round1(v float64) float64 {
	return math.Round(v*10) / 10
}

// topNAmenities returns the top N amenity counts sorted by frequency descending.
func topNAmenities(m map[string]int, n int) []AmenityCount {
	type kv struct {
		k string
		v int
	}
	var sorted []kv
	for k, v := range m {
		sorted = append(sorted, kv{k, v})
	}
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].v > sorted[j].v
	})
	result := make([]AmenityCount, 0, n)
	for i := 0; i < len(sorted) && i < n; i++ {
		result = append(result, AmenityCount{Name: sorted[i].k, Count: sorted[i].v})
	}
	return result
}

// topNLocations returns the top N location counts sorted by frequency descending.
func topNLocations(m map[string]int, n int) []LocationStat {
	type kv struct {
		k string
		v int
	}
	var sorted []kv
	for k, v := range m {
		sorted = append(sorted, kv{k, v})
	}
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].v > sorted[j].v
	})
	result := make([]LocationStat, 0, n)
	for i := 0; i < len(sorted) && i < n; i++ {
		result = append(result, LocationStat{Name: sorted[i].k, Count: sorted[i].v})
	}
	return result
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

// ReorderImages updates image positions. Uses two-phase update to avoid UNIQUE constraint.
func ReorderImages(db *sql.DB, listingID string, order []string) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Phase 1: set all positions to negative to avoid UNIQUE conflicts
	for i := range order {
		// Offset by -(len+1) so they don't collide with real positions
		negPos := -(i + 1) - len(order)
		_, err := tx.Exec("UPDATE listing_images SET position = ? WHERE listing_id = ? AND local_path = ?",
			negPos, listingID, order[i])
		if err != nil {
			return fmt.Errorf("reorder phase 1: %w", err)
		}
	}

	// Phase 2: set correct positions
	for i, path := range order {
		_, err := tx.Exec("UPDATE listing_images SET position = ? WHERE listing_id = ? AND local_path = ?",
			i, listingID, path)
		if err != nil {
			return fmt.Errorf("reorder phase 2: %w", err)
		}
	}
	return tx.Commit()
}

// CheckListingReady checks if listing HTML and PWA files exist on disk.
func CheckListingReady(listingID, listingsDir string) map[string]bool {
	result := map[string]bool{"html": false, "pwa": false}
	htmlPath := filepath.Join(listingsDir, listingID, "index.html")
	pwaPath := filepath.Join(listingsDir, listingID, "pwa-init.js")

	if _, err := os.Stat(htmlPath); err == nil {
		result["html"] = true
	}
	if _, err := os.Stat(pwaPath); err == nil {
		result["pwa"] = true
	}
	return result
}

// AddListingImage inserts a new image record for a listing.
func AddListingImage(db *sql.DB, listingID, imageURL, localPath string, position int) error {
	_, err := db.Exec(
		`INSERT INTO listing_images (listing_id, image_url, local_path, position) VALUES (?, ?, ?, ?)
		 ON CONFLICT(listing_id, position) DO UPDATE SET image_url=excluded.image_url, local_path=excluded.local_path`,
		listingID, imageURL, localPath, position)
	return err
}

// DeleteListingImage deletes a single image by local_path from a listing.
func DeleteListingImage(db *sql.DB, listingID, localPath string) error {
	_, err := db.Exec("DELETE FROM listing_images WHERE listing_id = ? AND local_path = ?", listingID, localPath)
	return err
}

// UpdateListingAddress updates a listing's address fields and map data.
func UpdateListingAddress(db *sql.DB, listingID, address, displayAddress string, lat, lng float64) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	now := time.Now().UTC().Format(time.RFC3339)
	_, err = tx.Exec(
		`UPDATE listings SET address=?, display_address=?, geocoding_address=?, updated_at=? WHERE id=?`,
		address, displayAddress, address, now, listingID)
	if err != nil {
		return fmt.Errorf("update listing address: %w", err)
	}

	_, err = tx.Exec(
		`INSERT INTO listing_map (listing_id, latitude, longitude, map_title) VALUES (?, ?, ?, ?)
		 ON CONFLICT(listing_id) DO UPDATE SET latitude=excluded.latitude, longitude=excluded.longitude, map_title=excluded.map_title`,
		listingID, lat, lng, displayAddress)
	if err != nil {
		return fmt.Errorf("update listing_map: %w", err)
	}

	return tx.Commit()
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
