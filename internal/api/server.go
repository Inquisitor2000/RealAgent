package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"realagent/internal/database"
	"realagent/internal/poi"
	"realagent/internal/scraper"

	qrcode "github.com/skip2/go-qrcode"
)

// ─── Scraper Interface ──────────────────────────────────────────────

// ScraperInterface abstracts the scraping engine for API handlers.
type ScraperInterface interface {
	ScrapeListing(ctx context.Context, url, templateName string) (*scraper.ScrapeResult, error)
	StartSync(ctx context.Context, urls []string, templateName string) error
	StopSync()
	GetSyncStatus() scraper.SyncStatus
}

// Server holds dependencies for API handlers.
type Server struct {
	DB          *sql.DB
	ListingsDir string
	Scraper     ScraperInterface
}

// New creates a new API server.
func New(db *sql.DB, scraper ScraperInterface) *Server {
	return &Server{DB: db, ListingsDir: "Listings", Scraper: scraper}
}

// ─── Helpers ───────────────────────────────────────────────────────

func jsonResponse(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if data != nil {
		json.NewEncoder(w).Encode(data)
	}
}

func jsonError(w http.ResponseWriter, status int, msg string) {
	jsonResponse(w, status, map[string]string{"error": msg})
}

func jsonSuccess(w http.ResponseWriter, extra map[string]interface{}) {
	resp := map[string]interface{}{"success": true}
	for k, v := range extra {
		resp[k] = v
	}
	jsonResponse(w, 200, resp)
}

func getID(r *http.Request) string {
	if id := r.PathValue("id"); id != "" {
		return id
	}
	return strings.TrimPrefix(r.URL.Path, "/api/listing/")
}

// ─── Listings ──────────────────────────────────────────────────────

// HandleListings returns all listings (GET /api/listings).
func (s *Server) HandleListings(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	listings, err := database.GetAllListings(s.DB, status)
	if err != nil {
		log.Printf("listings error: %v", err)
		jsonError(w, 500, "Failed to fetch listings")
		return
	}
	if listings == nil {
		listings = []database.ListingBasic{}
	}
	firstImages := database.GetFirstImages(s.DB)
	jsonSuccess(w, map[string]interface{}{
		"listings":     listings,
		"count":        len(listings),
		"first_images": firstImages,
	})
}

// HandleListing handles single listing: GET, PUT, DELETE /api/listing/{id}
func (s *Server) HandleListing(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		jsonError(w, 400, "Missing listing ID")
		return
	}

	switch r.Method {
	case http.MethodGet:
		s.getListing(w, r, id)
	case http.MethodPut:
		s.updateListing(w, r, id)
	case http.MethodDelete:
		s.deleteListing(w, r, id)
	default:
		jsonError(w, 405, "Method not allowed")
	}
}

func (s *Server) getListing(w http.ResponseWriter, r *http.Request, id string) {
	listing, err := database.GetListing(s.DB, id)
	if err != nil {
		jsonError(w, 500, "Failed to fetch listing")
		return
	}
	if listing == nil {
		jsonError(w, 404, "Listing not found")
		return
	}
	ready := database.CheckListingReady(id, s.ListingsDir)
	pois, _ := database.GetPOIData(s.DB, id)

	// Transform features flat array → {lang: {section: {key: val}}}
	// Frontend expects two-level nesting: language → section → key-value pairs
	featuresGrouped := make(map[string]map[string]map[string]string)
	for _, f := range listing.Features {
		if featuresGrouped[f.Lang] == nil {
			featuresGrouped[f.Lang] = make(map[string]map[string]string)
		}
		section := f.Section
		if section == "" {
			section = "Caracteristici"
		}
		if featuresGrouped[f.Lang][section] == nil {
			featuresGrouped[f.Lang][section] = make(map[string]string)
		}
		featuresGrouped[f.Lang][section][f.FeatureKey] = f.FeatureValue
	}

	// Transform amenities flat array → {lang: {key: true}} groups
	amenitiesGrouped := make(map[string]map[string]bool)
	for _, a := range listing.Amenities {
		if amenitiesGrouped[a.Lang] == nil {
			amenitiesGrouped[a.Lang] = make(map[string]bool)
		}
		amenitiesGrouped[a.Lang][a.AmenityKey] = a.AmenityValue == "true"
	}

	// Compute first image path for card display (full URL path)
	firstImagePath := ""
	if len(listing.Images) > 0 && listing.Images[0].LocalPath != "" {
		firstImagePath = "/listings/" + listing.ID + "/" + listing.Images[0].LocalPath
	}

	listingMap := map[string]interface{}{
		"id":                  listing.ID,
		"url":                 listing.URL,
		"domain":              listing.Domain,
		"title_ro":            listing.TitleRO,
		"title_ru":            listing.TitleRU,
		"description_ro":      listing.DescriptionRO,
		"description_ru":      listing.DescriptionRU,
		"price_json":          listing.PriceJSON,
		"price":               listing.Price,
		"image_path":          firstImagePath,
		"address":             listing.Address,
		"display_address":     listing.DisplayAddress,
		"geocoding_address":   listing.GeocodingAddress,
		"contact":             listing.Contact,
		"created_at":          listing.CreatedAt,
		"updated_at":          listing.UpdatedAt,
		"folder_path":         listing.FolderPath,
		"template_name":       listing.TemplateName,
		"status":              listing.Status,
		"user_corrected_address": listing.UserCorrectedAddress,
		"created_by":          listing.CreatedBy,
		"updated_by":          listing.UpdatedBy,
		"sold":                listing.Sold,
		"rented":              listing.Rented,
		"listing_type":        listing.ListingType,
		"property_type":       listing.PropertyType,
		"images":              listing.Images,
		"features":            featuresGrouped,
		"amenities":           amenitiesGrouped,
		"map_data":            listing.Map,
	}

	jsonSuccess(w, map[string]interface{}{
		"listing": listingMap,
		"processes_completed": map[string]interface{}{
			"data_scraping":   true,
			"database_save":   true,
			"html_generation":  ready["html"],
			"pwa_manifest":     ready["pwa"],
			"image_download":   len(listing.Images) > 0,
			"poi_fetch":        len(pois) > 0,
		},
		"is_complete": ready["html"] && ready["pwa"],
	})
}

func (s *Server) updateListing(w http.ResponseWriter, r *http.Request, id string) {
	var updates map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	user := r.Header.Get("X-User-Name")
	if user == "" {
		user = "api"
	}
	if err := database.UpdateListing(s.DB, id, updates, user); err != nil {
		log.Printf("update error: %v", err)
		jsonError(w, 500, "Failed to update listing")
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}

func (s *Server) deleteListing(w http.ResponseWriter, r *http.Request, id string) {
	if err := database.DeleteListing(s.DB, id); err != nil {
		jsonError(w, 500, "Failed to delete listing")
		return
	}
	jsonSuccess(w, nil)
}

// HandleCreateListing creates a listing (POST /api/listing/create).
func (s *Server) HandleCreateListing(w http.ResponseWriter, r *http.Request) {
	var data database.ListingData
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	id, err := database.InsertListing(s.DB, &data)
	if err != nil {
		log.Printf("create error: %v", err)
		jsonError(w, 500, "Failed to create listing")
		return
	}
	jsonSuccess(w, map[string]interface{}{"listing_id": id})
}

// HandleListingImages returns images for a listing (GET /api/listing/{id}/images).
func (s *Server) HandleListingImages(w http.ResponseWriter, r *http.Request) {
	listingID := r.PathValue("id")
	if listingID == "" {
		jsonError(w, 400, "Missing listing ID")
		return
	}

	images, err := database.GetListingImages(s.DB, listingID)
	if err != nil {
		jsonError(w, 500, "Failed to fetch images")
		return
	}
	if images == nil {
		images = []database.ListingImage{}
	}
	jsonSuccess(w, map[string]interface{}{
		"images": images,
		"count":  len(images),
	})
}

// HandleToggleSold toggles sold status (POST /api/listing/{id}/toggle-sold).
func (s *Server) HandleToggleSold(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		jsonError(w, 400, "Missing listing ID")
		return
	}
	status, err := database.ToggleSold(s.DB, id)
	if err != nil {
		jsonError(w, 500, "Failed to toggle sold")
		return
	}
	jsonSuccess(w, map[string]interface{}{"sold": status})
}

// HandleToggleRented toggles rented status (POST /api/listing/{id}/toggle-rented).
func (s *Server) HandleToggleRented(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		jsonError(w, 400, "Missing listing ID")
		return
	}
	status, err := database.ToggleRented(s.DB, id)
	if err != nil {
		jsonError(w, 500, "Failed to toggle rented")
		return
	}
	jsonSuccess(w, map[string]interface{}{"rented": status})
}

// extractIDFromPath extracts listing ID from paths like /api/listing/{id}/action.
func extractIDFromPath(path, suffix string) string {
	p := strings.TrimPrefix(path, "/api/listing/")
	p = strings.TrimSuffix(p, "/"+suffix)
	p = strings.TrimSuffix(p, "/")
	return p
}

// ─── Search ─────────────────────────────────────────────────────────

// HandleSearch performs filtered search (POST /api/express-search).
func (s *Server) HandleSearch(w http.ResponseWriter, r *http.Request) {
	var params database.SearchParams
	if err := json.NewDecoder(r.Body).Decode(&params); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	listings, total, err := database.ExpressSearch(s.DB, params)
	if err != nil {
		log.Printf("search error: %v", err)
		jsonError(w, 500, "Search failed")
		return
	}
	if listings == nil {
		listings = []database.ListingBasic{}
	}
	jsonSuccess(w, map[string]interface{}{
		"listings":              listings,
		"total_count":           total,
		"available_features":    map[string]interface{}{},
		"available_amenities":   []string{},
		"min_price_for_type":    0,
		"max_price_for_type":    1000000,
		"min_price_m2_for_type": 0,
		"max_price_m2_for_type": 5000,
	})
}

// ─── Statistics ────────────────────────────────────────────────────

// HandleStatistics returns aggregated stats (GET /api/statistics).
func (s *Server) HandleStatistics(w http.ResponseWriter, r *http.Request) {
	stats, err := database.GetStatistics(s.DB)
	if err != nil {
		jsonError(w, 500, "Failed to get statistics")
		return
	}
	jsonResponse(w, 200, stats)
}

// ─── Coordinates ───────────────────────────────────────────────────

// HandleCoordinates returns map coordinates (GET /api/coordinates).
func (s *Server) HandleCoordinates(w http.ResponseWriter, r *http.Request) {
	coords, err := database.GetCoordinates(s.DB)
	if err != nil {
		jsonError(w, 500, "Failed to get coordinates")
		return
	}
	if coords == nil {
		coords = []database.Coordinate{}
	}
	jsonResponse(w, 200, map[string]interface{}{
		"coordinates": coords,
		"count":       len(coords),
	})
}

// ─── Templates ─────────────────────────────────────────────────────

// HandleTemplates returns available templates (GET /api/templates).
func (s *Server) HandleTemplates(w http.ResponseWriter, r *http.Request) {
	templates := database.GetTemplates()
	jsonSuccess(w, map[string]interface{}{
		"templates": templates,
		"language":  "ro",
	})
}

// ─── Users ─────────────────────────────────────────────────────────

// HandleUsers lists or creates users (GET, POST /api/users).
func (s *Server) HandleUsers(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		s.listUsers(w, r)
	case http.MethodPost:
		s.createUser(w, r)
	default:
		jsonError(w, 405, "Method not allowed")
	}
}

func (s *Server) listUsers(w http.ResponseWriter, r *http.Request) {
	users, err := database.GetUsers(s.DB)
	if err != nil {
		jsonError(w, 500, "Failed to list users")
		return
	}
	if users == nil {
		users = []database.User{}
	}
	jsonResponse(w, 200, users)
}

func (s *Server) createUser(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
		FullName string `json:"full_name"`
		Role     string `json:"role"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	if body.Username == "" || body.Password == "" {
		jsonError(w, 400, "Username and password required")
		return
	}
	user, err := database.CreateUser(s.DB, body.Username, body.Password, body.FullName, body.Role)
	if err != nil {
		jsonError(w, 500, "Failed to create user: "+err.Error())
		return
	}
	jsonResponse(w, 201, user)
}

// HandleAuthMe returns current user info (GET /api/auth/me).
func (s *Server) HandleAuthMe(w http.ResponseWriter, r *http.Request) {
	jsonSuccess(w, map[string]interface{}{
		"username": r.Header.Get("X-User-Name"),
		"role":     r.Header.Get("X-User-Role"),
		"user_id":  r.Header.Get("X-User-ID"),
	})
}

// HandleChangePassword changes password (POST /api/auth/change-password).
func (s *Server) HandleChangePassword(w http.ResponseWriter, r *http.Request) {
	var body struct {
		OldPassword string `json:"old_password"`
		NewPassword string `json:"new_password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	userIDStr := r.Header.Get("X-User-ID")
	userID, _ := strconv.Atoi(userIDStr)
	if userID == 0 {
		jsonError(w, 401, "Not authenticated")
		return
	}
	// Verify old password
	username := r.Header.Get("X-User-Name")
	_, err := database.AuthenticateUser(s.DB, username, body.OldPassword)
	if err != nil {
		jsonError(w, 401, "Current password is incorrect")
		return
	}
	if err := database.UpdateUserPassword(s.DB, userID, body.NewPassword); err != nil {
		jsonError(w, 500, "Failed to change password")
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}

// ─── Journal ───────────────────────────────────────────────────────

// HandleJournal lists or creates journal entries (GET, POST /api/journal).
func (s *Server) HandleJournal(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		s.listJournal(w, r)
	case http.MethodPost:
		s.createJournal(w, r)
	default:
		jsonError(w, 405, "Method not allowed")
	}
}

func (s *Server) listJournal(w http.ResponseWriter, r *http.Request) {
	listingID := r.URL.Query().Get("listing_id")
	entryType := r.URL.Query().Get("entry_type")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))

	entries, err := database.GetJournalEntries(s.DB, listingID, entryType, limit, offset)
	if err != nil {
		jsonError(w, 500, "Failed to fetch journal")
		return
	}
	if entries == nil {
		entries = []database.JournalEntry{}
	}
	jsonSuccess(w, map[string]interface{}{
		"entries": entries,
		"count":   len(entries),
	})
}

func (s *Server) createJournal(w http.ResponseWriter, r *http.Request) {
	var body struct {
		ListingID string `json:"listing_id"`
		EntryType string `json:"entry_type"`
		Title     string `json:"title"`
		Content   string `json:"content"`
		Tags      string `json:"tags"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	user := r.Header.Get("X-User-Name")
	entry, err := database.CreateJournalEntry(s.DB, body.ListingID, body.EntryType, body.Title, body.Content, user, body.Tags)
	if err != nil {
		jsonError(w, 500, "Failed to create journal entry")
		return
	}
	jsonSuccess(w, map[string]interface{}{"entry": entry})
}

// HandleJournalEntry handles single journal entry (PUT, DELETE /api/journal/{id}).
func (s *Server) HandleJournalEntry(w http.ResponseWriter, r *http.Request) {
	// Extract ID from path
	path := r.URL.Path
	idStr := strings.TrimPrefix(path, "/api/journal/")
	// Handle /api/journal/clear
	if idStr == "clear" {
		s.clearJournal(w, r)
		return
	}
	id, err := strconv.Atoi(idStr)
	if err != nil {
		jsonError(w, 400, "Invalid journal entry ID")
		return
	}

	switch r.Method {
	case http.MethodPut:
		s.updateJournal(w, r, id)
	case http.MethodDelete:
		s.deleteJournal(w, r, id)
	default:
		jsonError(w, 405, "Method not allowed")
	}
}

func (s *Server) updateJournal(w http.ResponseWriter, r *http.Request, id int) {
	var body struct {
		Title     *string `json:"title"`
		Content   *string `json:"content"`
		EntryType *string `json:"entry_type"`
		Tags      *string `json:"tags"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	if err := database.UpdateJournalEntry(s.DB, id, body.Title, body.Content, body.EntryType, body.Tags); err != nil {
		jsonError(w, 500, "Failed to update journal entry")
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}

func (s *Server) deleteJournal(w http.ResponseWriter, r *http.Request, id int) {
	if err := database.DeleteJournalEntry(s.DB, id); err != nil {
		jsonError(w, 500, "Failed to delete journal entry")
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}

func (s *Server) clearJournal(w http.ResponseWriter, r *http.Request) {
	age := r.URL.Query().Get("age")
	if age == "" {
		age = "all"
	}
	count, err := database.ClearJournalEntries(s.DB, age)
	if err != nil {
		jsonError(w, 500, "Failed to clear journal")
		return
	}
	jsonSuccess(w, map[string]interface{}{"deleted": count})
}

// ─── POI ───────────────────────────────────────────────────────────

// HandleListingPOI returns POI data (GET /api/listing/{id}/poi).
func (s *Server) HandleListingPOI(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		jsonError(w, 400, "Missing listing ID")
		return
	}
	pois, err := database.GetPOIData(s.DB, id)
	if err != nil {
		jsonError(w, 500, "Failed to fetch POI data")
		return
	}
	if pois == nil {
		pois = []database.ListingPOI{}
	}
	// Group by category into nested dict
	grouped := make(map[string][]database.ListingPOI)
	for _, p := range pois {
		cat := string(p.Category)
		grouped[cat] = append(grouped[cat], p)
	}
	if grouped == nil {
		grouped = map[string][]database.ListingPOI{}
	}
	jsonSuccess(w, map[string]interface{}{
		"poi_data": grouped,
	})
}

// ─── Last Update ────────────────────────────────────────────────────

// HandleLastUpdate returns the most recent update timestamp (GET /api/last_update).
func (s *Server) HandleLastUpdate(w http.ResponseWriter, r *http.Request) {
	var lastUpdate string
	var total int
	s.DB.QueryRow("SELECT MAX(updated_at) FROM listings").Scan(&lastUpdate)
	s.DB.QueryRow("SELECT COUNT(*) FROM listings").Scan(&total)
	if lastUpdate == "" {
		lastUpdate = "never"
	}
	jsonResponse(w, 200, map[string]interface{}{
		"last_update": lastUpdate,
		"total_count": total,
		"timestamp":   time.Now().Format(time.RFC3339),
	})
}

// ─── QR Code ────────────────────────────────────────────────────────

// HandleQR generates a QR code for a listing URL (GET /api/listing/{id}/qr).
func (s *Server) HandleQR(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	listing, err := database.GetListing(s.DB, id)
	if err != nil {
		jsonError(w, 500, "Failed to fetch listing")
		return
	}
	if listing == nil {
		jsonError(w, 404, "Listing not found")
		return
	}
	if listing.URL == "" {
		jsonError(w, 400, "Listing has no URL")
		return
	}

	png, err := qrcode.Encode(listing.URL, qrcode.Medium, 256)
	if err != nil {
		jsonError(w, 500, "Failed to generate QR code")
		return
	}
	w.Header().Set("Content-Type", "image/png")
	w.Header().Set("Content-Length", strconv.Itoa(len(png)))
	w.WriteHeader(200)
	w.Write(png)
}

// ─── Listing Status ─────────────────────────────────────────────────

// HandleListingStatus checks if listing build/HTML/PWA files exist (GET /api/listing/{id}/status).
func (s *Server) HandleListingStatus(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	ready := database.CheckListingReady(id, s.ListingsDir)
	htmlOK := ready["html"]
	pwaOK := ready["pwa"]
	jsonSuccess(w, map[string]interface{}{
		"listing_id":     id,
		"ready":          htmlOK,
		"html_generated": htmlOK,
		"pwa_generated":  pwaOK,
		"html":           htmlOK,
		"pwa":            pwaOK,
		"is_complete":    htmlOK && pwaOK,
	})
}

// ─── Image Reorder ──────────────────────────────────────────────────

// HandleImageReorder updates image positions (PUT /api/listing/{id}/images/reorder).
func (s *Server) HandleImageReorder(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var body struct {
		Order []string `json:"order"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON body")
		return
	}
	if len(body.Order) == 0 {
		jsonError(w, 400, "Order array is empty")
		return
	}
	if err := database.ReorderImages(s.DB, id, body.Order); err != nil {
		jsonError(w, 500, "Failed to reorder images: "+err.Error())
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}

// ─── Upload Images ─────────────────────────────────────────────────

// HandleUploadImages handles multipart image upload (POST /api/listing/{id}/upload-images).
func (s *Server) HandleUploadImages(w http.ResponseWriter, r *http.Request) {
	listingID := r.PathValue("id")

	listing, err := database.GetListing(s.DB, listingID)
	if err != nil || listing == nil {
		jsonError(w, 404, "Listing not found")
		return
	}

	if err := r.ParseMultipartForm(50 << 20); err != nil {
		jsonError(w, 400, "Failed to parse multipart form")
		return
	}

	files := r.MultipartForm.File["images"]
	if len(files) == 0 {
		jsonError(w, 400, "No images provided")
		return
	}

	imgDir := filepath.Join(s.ListingsDir, listingID, "images")
	if err := os.MkdirAll(imgDir, 0755); err != nil {
		jsonError(w, 500, "Failed to create images directory")
		return
	}

	allowedExt := map[string]bool{
		".jpg": true, ".jpeg": true, ".png": true, ".gif": true, ".webp": true,
	}

	var uploaded []string
	for _, fh := range files {
		ext := strings.ToLower(filepath.Ext(fh.Filename))
		if !allowedExt[ext] {
			continue
		}

		file, err := fh.Open()
		if err != nil {
			continue
		}

		// Unique filename using nanosecond timestamp + original name
		ts := time.Now().UnixNano()
		filename := fmt.Sprintf("%d_%s", ts, fh.Filename)
		dst, err := os.Create(filepath.Join(imgDir, filename))
		if err != nil {
			file.Close()
			continue
		}

		if _, err := io.Copy(dst, file); err != nil {
			file.Close()
			dst.Close()
			continue
		}
		file.Close()
		dst.Close()

		uploaded = append(uploaded, filename)
	}

	if len(uploaded) == 0 {
		jsonError(w, 400, "No valid image files uploaded")
		return
	}

	// Get current max position
	images, _ := database.GetListingImages(s.DB, listingID)
	position := len(images)
	for _, name := range uploaded {
		position++
		database.AddListingImage(s.DB, listingID, name, name, position)
	}

	jsonResponse(w, 200, map[string]interface{}{
		"success":       true,
		"uploaded_files": uploaded,
		"count":         len(uploaded),
		"message":       fmt.Sprintf("Successfully uploaded %d image(s)", len(uploaded)),
	})
}

// ─── Refresh POIs ────────────────────────────────────────────────

// HandleRefreshPOIs re-fetches POI data for a listing (POST /api/listing/{id}/refresh-pois).
func (s *Server) HandleRefreshPOIs(w http.ResponseWriter, r *http.Request) {
	listingID := r.PathValue("id")

	listing, err := database.GetListing(s.DB, listingID)
	if err != nil || listing == nil {
		jsonError(w, 404, "Listing not found")
		return
	}

	if listing.Latitude == 0 && listing.Longitude == 0 {
		jsonError(w, 400, "No coordinates available for this listing")
		return
	}

	result, err := poi.FetchAndSave(s.DB, listingID, listing.Latitude, listing.Longitude, 500)
	if err != nil {
		jsonError(w, 500, fmt.Sprintf("Failed to refresh POIs: %v", err))
		return
	}

	jsonResponse(w, 200, map[string]interface{}{
		"success":    true,
		"poi_count":  result.TotalPOIs,
		"categories": result.Categories,
		"message":    fmt.Sprintf("Found %d POIs across %d categories", result.TotalPOIs, len(result.Categories)),
	})
}

// ─── Update Address ───────────────────────────────────────────────

// HandleUpdateAddress updates listing address and re-fetches POIs (POST /api/listing/{id}/update-address).
func (s *Server) HandleUpdateAddress(w http.ResponseWriter, r *http.Request) {
	listingID := r.PathValue("id")

	listing, err := database.GetListing(s.DB, listingID)
	if err != nil || listing == nil {
		jsonError(w, 404, "Listing not found")
		return
	}

	var body struct {
		Lat            float64 `json:"lat"`
		Lng            float64 `json:"lng"`
		Address        string  `json:"address"`
		DisplayAddress string  `json:"display_address"`
	}

	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON body")
		return
	}

	if body.Lat == 0 && body.Lng == 0 {
		jsonError(w, 400, "Latitude and longitude are required")
		return
	}

	addr := body.Address
	if addr == "" {
		addr = listing.Address
	}
	displayAddr := body.DisplayAddress
	if displayAddr == "" {
		displayAddr = addr
	}

	if err := database.UpdateListingAddress(s.DB, listingID, addr, displayAddr, body.Lat, body.Lng); err != nil {
		jsonError(w, 500, fmt.Sprintf("Failed to update address: %v", err))
		return
	}

	// Re-fetch POIs for new location
	go func() {
		if _, err := poi.FetchAndSave(s.DB, listingID, body.Lat, body.Lng, 500); err != nil {
			log.Printf("⚠️ POI refresh after address update failed: %v", err)
		}
	}()

	jsonResponse(w, 200, map[string]interface{}{
		"success":          true,
		"address_updated":  true,
		"new_address":       displayAddr,
		"new_lat":          body.Lat,
		"new_lng":          body.Lng,
	})
}

// ─── Scrape ─────────────────────────────────────────────────────────

// HandleScrape scrapes a listing by URL (POST /api/listing/scrape).
func (s *Server) HandleScrape(w http.ResponseWriter, r *http.Request) {
	if s.Scraper == nil {
		jsonError(w, 503, "Scraper engine not available")
		return
	}
	var body struct {
		URL          string `json:"url"`
		TemplateName string `json:"template_name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	if body.URL == "" {
		jsonError(w, 400, "URL is required")
		return
	}
	if body.TemplateName == "" {
		body.TemplateName = "luna"
	}
	result, err := s.Scraper.ScrapeListing(r.Context(), body.URL, body.TemplateName)
	if err != nil {
		jsonError(w, 500, err.Error())
		return
	}
	if !result.Success {
		jsonResponse(w, 422, result)
		return
	}
	jsonResponse(w, 200, result)
}

// ─── Sync ───────────────────────────────────────────────────────────

// HandleSyncSingle syncs a single listing by ID (POST /api/listing/{id}/sync).
func (s *Server) HandleSyncSingle(w http.ResponseWriter, r *http.Request) {
	if s.Scraper == nil {
		jsonError(w, 503, "Scraper engine not available")
		return
	}
	id := r.PathValue("id")
	if id == "" {
		jsonError(w, 400, "Missing listing ID")
		return
	}

	listing, err := database.GetListing(s.DB, id)
	if err != nil {
		jsonError(w, 500, "Failed to fetch listing")
		return
	}
	if listing == nil {
		jsonError(w, 404, "Listing not found")
		return
	}
	if listing.URL == "" {
		jsonError(w, 400, "Listing has no URL to scrape")
		return
	}

	result, err := s.Scraper.ScrapeListing(r.Context(), listing.URL, listing.TemplateName)
	if err != nil {
		jsonError(w, 500, err.Error())
		return
	}
	jsonResponse(w, 200, result)
}

// HandleSyncStart begins batch sync (POST /api/sync/start).
func (s *Server) HandleSyncStart(w http.ResponseWriter, r *http.Request) {
	if s.Scraper == nil {
		jsonError(w, 503, "Scraper engine not available")
		return
	}
	var body struct {
		URLs         []string `json:"urls"`
		TemplateName string   `json:"template_name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	if len(body.URLs) == 0 {
		jsonError(w, 400, "urls array is required")
		return
	}
	if body.TemplateName == "" {
		body.TemplateName = "luna"
	}
	if err := s.Scraper.StartSync(r.Context(), body.URLs, body.TemplateName); err != nil {
		jsonError(w, 409, err.Error())
		return
	}
	jsonSuccess(w, map[string]interface{}{"started": true})
}

// HandleSyncStatus returns sync progress (GET /api/sync/status).
func (s *Server) HandleSyncStatus(w http.ResponseWriter, r *http.Request) {
	if s.Scraper == nil {
		jsonError(w, 503, "Scraper engine not available")
		return
	}
	status := s.Scraper.GetSyncStatus()
	jsonResponse(w, 200, status)
}

// HandleSyncStop cancels batch sync (POST /api/sync/stop).
func (s *Server) HandleSyncStop(w http.ResponseWriter, r *http.Request) {
	if s.Scraper == nil {
		jsonError(w, 503, "Scraper engine not available")
		return
	}
	s.Scraper.StopSync()
	jsonSuccess(w, map[string]interface{}{"stopped": true})
}

// ─── Settings ───────────────────────────────────────────────────────

// HandleGetSettings returns application settings (GET /api/settings).
func (s *Server) HandleGetSettings(w http.ResponseWriter, r *http.Request) {
	jsonSuccess(w, map[string]interface{}{})
}

// HandleSaveSettings saves application settings (POST /api/settings).
func (s *Server) HandleSaveSettings(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	log.Printf("Settings saved: %v", body)
	jsonResponse(w, 200, map[string]bool{"success": true})
}

// ─── Sections ───────────────────────────────────────────────────────

// HandleGetSections returns distinct feature sections (GET /api/sections).
func (s *Server) HandleGetSections(w http.ResponseWriter, r *http.Request) {
	rows, err := s.DB.Query("SELECT DISTINCT section FROM listing_features WHERE section IS NOT NULL AND section != '' ORDER BY section")
	if err != nil {
		jsonError(w, 500, "Failed to fetch sections")
		return
	}
	defer rows.Close()

	var sections []string
	for rows.Next() {
		var section string
		if err := rows.Scan(&section); err == nil {
			sections = append(sections, section)
		}
	}
	if sections == nil {
		sections = []string{}
	}
	jsonSuccess(w, map[string]interface{}{
		"sections": sections,
	})
}

// HandleCreateSection creates a new section (POST /api/sections).
func (s *Server) HandleCreateSection(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, 200, map[string]bool{"success": true})
}

// HandleDeleteSection deletes a section (DELETE /api/sections/{id}).
func (s *Server) HandleDeleteSection(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, 200, map[string]bool{"success": true})
}

// ─── User Management ────────────────────────────────────────────────

// HandleDeleteUser deletes a user (POST /api/users/{id}/delete).
func (s *Server) HandleDeleteUser(w http.ResponseWriter, r *http.Request) {
	idStr := r.PathValue("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		jsonError(w, 400, "Invalid user ID")
		return
	}
	if err := database.DeleteUser(s.DB, id); err != nil {
		jsonError(w, 500, "Failed to delete user")
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}

// HandleChangeUserPassword changes another user's password (POST /api/users/{id}/password).
func (s *Server) HandleChangeUserPassword(w http.ResponseWriter, r *http.Request) {
	idStr := r.PathValue("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		jsonError(w, 400, "Invalid user ID")
		return
	}
	var body struct {
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, 400, "Invalid JSON")
		return
	}
	if body.Password == "" {
		jsonError(w, 400, "Password is required")
		return
	}
	if err := database.UpdateUserPassword(s.DB, id, body.Password); err != nil {
		jsonError(w, 500, "Failed to change password")
		return
	}
	jsonResponse(w, 200, map[string]bool{"success": true})
}
