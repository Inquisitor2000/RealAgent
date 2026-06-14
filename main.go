package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"realagent/internal/api"
	"realagent/internal/database"
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
	sessKey   = []byte("realagent-session-key-change-me") // TODO: env var
)

const sessionName = "ra_session"

// ─── Data Types ───────────────────────────────────────────────────

type User struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	FullName string `json:"full_name"`
	Role     string `json:"role"`
}

type DashboardData struct {
	User     User
	Listings []database.ListingBasic
	Stats    database.ListingStats
	Flash    *FlashMsg
}

type FlashMsg struct {
	Type    string
	Message string
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

	data := DashboardData{
		User:     *user,
		Listings: listings,
		Stats:    *stats,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := templates.ExecuteTemplate(w, "dashboard.html", data); err != nil {
		log.Printf("Template error: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
	}
}

// ─── Route Registration ───────────────────────────────────────────

func registerRoutes(mux *http.ServeMux, apiSrv *api.Server) {
	// Static files
	staticFS := http.FileServer(http.FS(content))
	mux.Handle("GET /static/", staticFS)
	mux.Handle("GET /pwa/", staticFS)

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

	// Dashboard (auth required)
	mux.Handle("GET /", authMiddleware(handleDashboard))

	// ─── API Routes ─────────────────────────────────────────────

	// Listings
	mux.HandleFunc("GET /api/listings", apiSrv.HandleListings)
	mux.HandleFunc("POST /api/listing/create", apiSrv.HandleCreateListing)
	
	// Listing by ID (sub-resources must be registered first for specificity)
	mux.HandleFunc("GET /api/listing/{id}/images", apiSrv.HandleListingImages)
	mux.HandleFunc("POST /api/listing/{id}/toggle-sold", apiSrv.HandleToggleSold)
	mux.HandleFunc("POST /api/listing/{id}/toggle-rented", apiSrv.HandleToggleRented)
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

	// Journal
	mux.HandleFunc("GET /api/journal", apiSrv.HandleJournal)
	mux.HandleFunc("POST /api/journal", apiSrv.HandleJournal)
	mux.HandleFunc("PUT /api/journal/", apiSrv.HandleJournalEntry)
	mux.HandleFunc("DELETE /api/journal/", apiSrv.HandleJournalEntry)
}

// ─── Main ──────────────────────────────────────────────────────────

func main() {
	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "Mainframe.db"
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}

	// Open database
	var err error
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

	// Parse templates
	templates = template.Must(template.ParseFS(content, "web/templates/go/*.html"))
	log.Printf("✅ Templates loaded")

	// Create API server
	apiSrv := api.New(db)

	// Register routes
	mux := http.NewServeMux()
	registerRoutes(mux, apiSrv)

	log.Printf("🚀 RealAgent starting on :%s", port)
	log.Printf("   Open http://localhost:%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
