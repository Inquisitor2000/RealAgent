package main

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html/template"
	"io/fs"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"realagent/internal/api"
	"realagent/internal/database"
	"realagent/internal/scraper"
)

// ─── Embedded Assets ───────────────────────────────────────────────

//go:embed web/templates/go/*
//go:embed web/static/*
//go:embed web/pwa/assets/*
//go:embed web/pwa/manifest.json
//go:embed web/pwa/offline.html
//go:embed web/pwa/pwa-init.js
//go:embed web/pwa/service-worker.js
var content embed.FS

// ─── Globals ───────────────────────────────────────────────────────

var (
	db        *sql.DB
	templates *template.Template
	sessKey   []byte
)

func init() {
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		log.Fatalf("Failed to generate session key: %v", err)
	}
	sessKey = key
}

const sessionName = "ra_session"

// ─── Data Types ───────────────────────────────────────────────────

type User struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	FullName string `json:"full_name"`
	Role     string `json:"role"`
}

// ListingCard wraps ListingBasic with computed display fields for the template.
type ListingCard struct {
	database.ListingBasic
	DisplayPrice string `json:"display_price"`
	PriceNumeric string `json:"price_numeric"`
	FirstImage   string `json:"first_image"`
}

type DashboardData struct {
	User     User
	Listings []ListingCard
	Stats    database.ListingStats
	Flash    *FlashMsg
}

type FlashMsg struct {
	Type    string
	Message string
}

// ─── Template Functions ───────────────────────────────────────────

// tmplFuncs returns custom functions for Go templates.
func tmplFuncs() template.FuncMap {
	return template.FuncMap{
		"default": func(def, val string) string {
			if val == "" {
				return def
			}
			return val
		},
		"slice": func(s string, max int) string {
			if len(s) > max {
				return s[:max]
			}
			return s
		},
	}
}

// ─── Session Helpers ──────────────────────────────────────────────

func encodeSession(user User) string {
	data := fmt.Sprintf("%d|%s|%s|%d", user.ID, user.Username, user.Role, time.Now().Unix())
	mac := hmac.New(sha256.New, sessKey)
	mac.Write([]byte(data))
	sig := hex.EncodeToString(mac.Sum(nil))
	return hex.EncodeToString([]byte(data)) + "." + sig
}

func decodeSession(token string) (*User, bool) {
	parts := strings.SplitN(token, ".", 2)
	if len(parts) != 2 {
		return nil, false
	}
	dataBytes, err := hex.DecodeString(parts[0])
	if err != nil {
		return nil, false
	}
	data := string(dataBytes)

	mac := hmac.New(sha256.New, sessKey)
	mac.Write(dataBytes)
	expected := hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(parts[1]), []byte(expected)) {
		return nil, false
	}

	parts2 := strings.SplitN(data, "|", 4)
	if len(parts2) < 3 {
		return nil, false
	}
	var user User
	fmt.Sscanf(parts2[0], "%d", &user.ID)
	user.Username = parts2[1]
	user.Role = parts2[2]
	return &user, true
}

func getUser(r *http.Request) *User {
	c, err := r.Cookie(sessionName)
	if err != nil {
		return nil
	}
	user, ok := decodeSession(c.Value)
	if !ok {
		return nil
	}
	return user
}

func setUser(w http.ResponseWriter, user User) {
	token := encodeSession(user)
	http.SetCookie(w, &http.Cookie{
		Name:     sessionName,
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   86400 * 7,
	})
}

func clearSession(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     sessionName,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
	})
}

// ─── Middleware ────────────────────────────────────────────────────

func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		user := getUser(r)
		if user == nil {
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		r.Header.Set("X-User-Name", user.Username)
		r.Header.Set("X-User-ID", fmt.Sprintf("%d", user.ID))
		r.Header.Set("X-User-Role", user.Role)
		next(w, r)
	}
}

func apiAuthMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		user := getUser(r)
		if user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			json.NewEncoder(w).Encode(map[string]string{"error": "Unauthorized"})
			return
		}
		r.Header.Set("X-User-Name", user.Username)
		r.Header.Set("X-User-ID", fmt.Sprintf("%d", user.ID))
		r.Header.Set("X-User-Role", user.Role)
		next(w, r)
	}
}

// ─── Handlers ─────────────────────────────────────────────────────

func handleLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		handleLoginPost(w, r)
		return
	}
	if getUser(r) != nil {
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	templates.ExecuteTemplate(w, "login.html", nil)
}

func handleLoginPost(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": "Invalid request"})
		return
	}

	user, err := database.AuthenticateUser(db, strings.TrimSpace(body.Username), body.Password)
	if err != nil {
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	u := User{ID: user.ID, Username: user.Username, FullName: user.FullName, Role: user.Role}
	setUser(w, u)
	log.Printf("✅ User logged in: %s (%s)", user.Username, user.Role)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"user": map[string]string{
			"username":  user.Username,
			"full_name": user.FullName,
			"role":      user.Role,
		},
	})
}

func handleLogout(w http.ResponseWriter, r *http.Request) {
	clearSession(w)
	http.Redirect(w, r, "/login", http.StatusSeeOther)
}

func handleApiLogout(w http.ResponseWriter, r *http.Request) {
	clearSession(w)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"message": "Logged out successfully",
	})
}

func handleDashboard(w http.ResponseWriter, r *http.Request) {
	user := getUser(r)
	if user == nil {
		http.Redirect(w, r, "/login", http.StatusSeeOther)
		return
	}

	listings, err := database.GetAllListings(db, "all")
	if err != nil {
		listings = []database.ListingBasic{}
	}
	stats, err := database.GetStatistics(db)
	if err != nil {
		stats = &database.ListingStats{}
	}

	// Fetch first image for each listing
	firstImages := database.GetFirstImages(db)

	// Build listing cards with computed display fields
	cards := make([]ListingCard, len(listings))
	for i, l := range listings {
		cards[i] = ListingCard{
			ListingBasic: l,
			DisplayPrice: l.Price,
			PriceNumeric: extractNumericPrice(l.PriceJSON),
			FirstImage:   firstImages[l.ID],
		}
	}

	data := DashboardData{
		User:     *user,
		Listings: cards,
		Stats:    *stats,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := templates.ExecuteTemplate(w, "dashboard.html", data); err != nil {
		log.Printf("Template error: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
	}
}

// extractNumericPrice pulls a numeric value from PriceJSON for sorting.
func extractNumericPrice(priceJSON string) string {
	if priceJSON == "" || priceJSON == "{}" {
		return "0"
	}
	var prices map[string]interface{}
	if err := json.Unmarshal([]byte(priceJSON), &prices); err != nil {
		return "0"
	}
	// Prefer EUR
	if v, ok := prices["EUR"]; ok {
		return fmt.Sprintf("%v", v)
	}
	if v, ok := prices["MDL"]; ok {
		return fmt.Sprintf("%v", v)
	}
	return "0"
}

// serveEmbed returns a handler that serves a single embedded file.
func serveEmbed(path, contentType string) func(w http.ResponseWriter, r *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		data, err := content.ReadFile(path)
		if err != nil {
			http.Error(w, "Not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", contentType)
		w.Write(data)
	}
}

// ─── Route Registration ───────────────────────────────────────────

func registerRoutes(mux *http.ServeMux, apiSrv *api.Server) {
	// Static files (using fs.Sub to strip web/ prefix from embed paths)
	staticRoot, _ := fs.Sub(content, "web/static")
	pwaRoot, _ := fs.Sub(content, "web/pwa")
	staticFS := http.FileServer(http.FS(staticRoot))
	mux.Handle("GET /static/", http.StripPrefix("/static/", staticFS))
	mux.Handle("GET /pwa/assets/", http.StripPrefix("/pwa/assets/", http.FileServer(http.FS(pwaRoot))))
	mux.HandleFunc("GET /pwa/manifest.json", serveEmbed("web/pwa/manifest.json", "application/json"))
	mux.HandleFunc("GET /pwa/service-worker.js", serveEmbed("web/pwa/service-worker.js", "application/javascript"))
	mux.HandleFunc("GET /pwa/pwa-init.js", serveEmbed("web/pwa/pwa-init.js", "application/javascript"))
	mux.HandleFunc("GET /pwa/offline.html", serveEmbed("web/pwa/offline.html", "text/html"))

	// Dashboard CSS at root path
	mux.HandleFunc("GET /dashboard.css", func(w http.ResponseWriter, r *http.Request) {
		data, err := content.ReadFile("web/static/dashboard.css")
		if err != nil {
			http.Error(w, "Not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "text/css")
		w.Write(data)
	})

	// Auth pages
	mux.HandleFunc("GET /login", handleLogin)
	mux.HandleFunc("POST /api/auth/login", handleLoginPost)
	mux.Handle("POST /logout", http.HandlerFunc(handleLogout))
	mux.Handle("GET /logout", http.HandlerFunc(handleLogout))
	mux.HandleFunc("POST /api/auth/logout", handleApiLogout)

	// Dashboard (auth required)
	mux.Handle("GET /", authMiddleware(handleDashboard))

	// ─── API Routes ─────────────────────────────────────────────

	// Listings
	mux.HandleFunc("GET /api/listings", apiSrv.HandleListings)
	mux.HandleFunc("POST /api/listing/create", apiSrv.HandleCreateListing)
	
	// Listing by ID (sub-resources must be registered first for specificity)
	mux.HandleFunc("GET /api/listing/{id}/images", apiSrv.HandleListingImages)
	mux.HandleFunc("POST /api/listings/{id}/toggle-sold", apiSrv.HandleToggleSold)
	mux.HandleFunc("POST /api/listings/{id}/toggle-rented", apiSrv.HandleToggleRented)
	mux.HandleFunc("GET /api/listing/{id}/poi", apiSrv.HandleListingPOI)
	mux.HandleFunc("GET /api/listing/{id}", apiSrv.HandleListing)
	mux.HandleFunc("PUT /api/listing/{id}", apiSrv.HandleListing)
	mux.HandleFunc("DELETE /api/listing/{id}", apiSrv.HandleListing)

	// Search
	mux.HandleFunc("POST /api/express-search", apiSrv.HandleSearch)

	// Data
	mux.HandleFunc("GET /api/statistics", apiSrv.HandleStatistics)
	mux.HandleFunc("GET /api/coordinates", apiSrv.HandleCoordinates)
	mux.HandleFunc("GET /api/last_update", apiSrv.HandleLastUpdate)
	mux.HandleFunc("GET /api/templates", apiSrv.HandleTemplates)

	// Users (admin-only via middleware)
	mux.Handle("GET /api/users", apiAuthMiddleware(apiSrv.HandleUsers))
	mux.Handle("POST /api/users", apiAuthMiddleware(apiSrv.HandleUsers))

	// Auth API
	mux.Handle("GET /api/auth/me", apiAuthMiddleware(apiSrv.HandleAuthMe))
	mux.Handle("POST /api/auth/change-password", apiAuthMiddleware(apiSrv.HandleChangePassword))

	// QR code
	mux.HandleFunc("GET /api/listing/{id}/qr", apiSrv.HandleQR)

	// Listing status / images
	mux.HandleFunc("GET /api/listing/{id}/status", apiSrv.HandleListingStatus)
	mux.HandleFunc("PUT /api/listing/{id}/images/reorder", apiSrv.HandleImageReorder)
	mux.HandleFunc("POST /api/listing/{id}/upload-images", apiSrv.HandleUploadImages)
	mux.HandleFunc("POST /api/listing/{id}/refresh-pois", apiSrv.HandleRefreshPOIs)
	mux.HandleFunc("POST /api/listing/{id}/update-address", apiSrv.HandleUpdateAddress)

	// Scrape
	mux.HandleFunc("POST /api/listing/scrape", apiSrv.HandleScrape)
	mux.HandleFunc("POST /api/listing/{id}/sync", apiSrv.HandleSyncSingle)

	// Sync batch
	mux.HandleFunc("POST /api/sync/start", apiSrv.HandleSyncStart)
	mux.HandleFunc("GET /api/sync/status", apiSrv.HandleSyncStatus)
	mux.HandleFunc("POST /api/sync/stop", apiSrv.HandleSyncStop)

	// Settings
	mux.HandleFunc("GET /api/settings", apiSrv.HandleGetSettings)
	mux.HandleFunc("POST /api/settings", apiSrv.HandleSaveSettings)

	// Sections
	mux.HandleFunc("GET /api/sections", apiSrv.HandleGetSections)
	mux.HandleFunc("POST /api/sections", apiSrv.HandleCreateSection)
	mux.HandleFunc("DELETE /api/sections/{id}", apiSrv.HandleDeleteSection)

	// User management
	mux.HandleFunc("POST /api/users/{id}/delete", apiSrv.HandleDeleteUser)
	mux.HandleFunc("POST /api/users/{id}/password", apiSrv.HandleChangeUserPassword)

	// File serving for generated listing pages and promotional files
	listingsDir := http.Dir(apiSrv.ListingsDir)
	promoDir := http.Dir("Templates/Promotional")
	mux.Handle("GET /listings/", http.StripPrefix("/listings/", http.FileServer(listingsDir)))
	mux.Handle("GET /promotional/", http.StripPrefix("/promotional/", http.FileServer(promoDir)))
}

// ─── Main ──────────────────────────────────────────────────────────

func main() {
	// Determine binary directory for default paths (handles double-click scenarios
	// where CWD is the home directory, not the binary location).
	execPath, err := os.Executable()
	if err != nil {
		log.Fatalf("Failed to get executable path: %v", err)
	}
	binDir := filepath.Dir(execPath)

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = filepath.Join(binDir, "Mainframe.db")
	}
	listingsDir := os.Getenv("LISTINGS_DIR")
	if listingsDir == "" {
		listingsDir = filepath.Join(binDir, "Listings")
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}

	// Open database
	db, err = database.OpenDB(dbPath)
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()
	log.Printf("✅ Connected to database: %s", dbPath)

	// Initialize schema (idempotent)
	if err := database.InitSchema(db); err != nil {
		log.Fatalf("Failed to initialize schema: %v", err)
	}
	log.Printf("✅ Schema initialized")

	// Seed default user if empty
	if err := database.SeedDefaultUser(db); err != nil {
		log.Printf("⚠️ Seed user failed: %v", err)
	}

	// Parse templates with custom functions
	templates = template.Must(template.New("").Funcs(tmplFuncs()).ParseFS(content, "web/templates/go/*.html"))
	log.Printf("✅ Templates loaded")

	// Create scraper engine
	scr := scraper.New(nil, db, listingsDir)

	// Create API server
	apiSrv := api.New(db, scr, listingsDir)

	// Register routes
	mux := http.NewServeMux()
	registerRoutes(mux, apiSrv)

	srv := &http.Server{
		Addr:    ":" + port,
		Handler: mux,
	}

	// Graceful shutdown on SIGINT/SIGTERM
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-quit
		log.Println("⏳ Shutting down server...")

		// Rotate session key — all existing sessions invalidated
		key := make([]byte, 32)
		if _, err := rand.Read(key); err == nil {
			sessKey = key
		}

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Fatalf("Server forced to shutdown: %v", err)
		}
		log.Println("✅ Server stopped gracefully")
	}()

	log.Printf("🚀 RealAgent starting on :%s", port)
	log.Printf("   Open http://localhost:%s", port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server failed: %v", err)
	}
}
