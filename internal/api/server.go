package api

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"strings"

	"realagent/internal/database"
)

// Server holds dependencies for API handlers.
type Server struct {
	DB *sql.DB
}

// New creates a new API server.
func New(db *sql.DB) *Server {
	return &Server{DB: db}
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
	jsonResponse(w, 200, listings)
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
	jsonResponse(w, 200, listing)
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
	jsonResponse(w, 200, map[string]bool{"success": true})
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
	jsonResponse(w, 201, map[string]string{"id": id})
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
	jsonResponse(w, 200, images)
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
	jsonResponse(w, 200, map[string]string{"sold": status})
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
	jsonResponse(w, 200, map[string]string{"rented": status})
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
	jsonResponse(w, 200, map[string]interface{}{
		"listings": listings,
		"total":    total,
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
	jsonResponse(w, 200, coords)
}

// ─── Templates ─────────────────────────────────────────────────────

// HandleTemplates returns available templates (GET /api/templates).
func (s *Server) HandleTemplates(w http.ResponseWriter, r *http.Request) {
	templates := database.GetTemplates()
	jsonResponse(w, 200, templates)
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
	jsonResponse(w, 200, map[string]string{
		"username":  r.Header.Get("X-User-Name"),
		"role":      r.Header.Get("X-User-Role"),
		"user_id":   r.Header.Get("X-User-ID"),
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
	jsonResponse(w, 200, entries)
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
	jsonResponse(w, 201, entry)
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
	jsonResponse(w, 200, map[string]interface{}{"deleted": count})
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
	jsonResponse(w, 200, pois)
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
		"total":       total,
	})
}
