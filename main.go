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

	_ "modernc.org/sqlite"
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
	Active   bool   `json:"active"`
}

type Listing struct {
	ID        int
	URL       string
	TitleRO   string
	TitleRU   string
	Price     string
	Address   string
	Status    string
	CreatedAt string
	UpdatedAt string
}

type DashboardData struct {
	User     User
	Listings []Listing
	Stats    Stats
	Flash    *FlashMsg
}

type Stats struct {
	Total  int
	Active int
	Sold   int
	Rented int
}

type FlashMsg struct {
	Type    string // "success" or "error"
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
		MaxAge:   86400 * 7, // 7 days
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

// ─── Auth ──────────────────────────────────────────────────────────

func authenticateUser(username, password string) (*User, error) {
	hash := sha256.Sum256([]byte(password))
	passwordHash := hex.EncodeToString(hash[:])

	var u User
	err := db.QueryRow(`
		SELECT id, username, full_name, role, active
		FROM users WHERE username = ? AND password_hash = ?
	`, username, passwordHash).Scan(&u.ID, &u.Username, &u.FullName, &u.Role, &u.Active)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("invalid credentials")
	}
	if err != nil {
		return nil, err
	}
	if !u.Active {
		return nil, fmt.Errorf("account disabled")
	}
	return &u, nil
}

// ─── DB Queries ───────────────────────────────────────────────────

func getListings(status string) ([]Listing, error) {
	query := `
		SELECT id, url, title_ro, title_ru, price_json, address, status,
			   created_at, updated_at
		FROM listings
	`
	var args []interface{}
	if status != "all" {
		query += " WHERE status = ?"
		args = append(args, status)
	}
	query += " ORDER BY created_at DESC"

	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var listings []Listing
	for rows.Next() {
		var l Listing
		var priceJSON, createdAt, updatedAt sql.NullString
		err := rows.Scan(&l.ID, &l.URL, &l.TitleRO, &l.TitleRU,
			&priceJSON, &l.Address, &l.Status,
			&createdAt, &updatedAt)
		if err != nil {
			return nil, err
		}
		if priceJSON.Valid {
			l.Price = priceJSON.String
		}
		if createdAt.Valid {
			l.CreatedAt = createdAt.String
		}
		if updatedAt.Valid {
			l.UpdatedAt = updatedAt.String
		}
		listings = append(listings, l)
	}
	return listings, nil
}

func getStats() (*Stats, error) {
	var s Stats
	err := db.QueryRow("SELECT COUNT(*) FROM listings").Scan(&s.Total)
	if err != nil {
		return nil, err
	}
	db.QueryRow("SELECT COUNT(*) FROM listings WHERE status = 'active'").Scan(&s.Active)
	db.QueryRow("SELECT COUNT(*) FROM listings WHERE sold = 1").Scan(&s.Sold)
	db.QueryRow("SELECT COUNT(*) FROM listings WHERE rented = 1").Scan(&s.Rented)
	return &s, nil
}

// ─── Middleware ────────────────────────────────────────────────────

func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		user := getUser(r)
		if user == nil {
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		// Store user in context for handlers
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

	// Already logged in? redirect to /
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
		json.NewEncoder(w).Encode(map[string]interface{}{
			"success": false, "error": "Invalid request",
		})
		return
	}

	user, err := authenticateUser(strings.TrimSpace(body.Username), body.Password)
	if err != nil {
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"success": false, "error": err.Error(),
		})
		return
	}

	setUser(w, *user)
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

	listings, err := getListings("all")
	if err != nil {
		log.Printf("Error fetching listings: %v", err)
		listings = []Listing{}
	}

	stats, err := getStats()
	if err != nil {
		stats = &Stats{}
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

func handleAPIListings(w http.ResponseWriter, r *http.Request) {
	user := getUser(r)
	if user == nil {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	status := r.URL.Query().Get("status")
	if status == "" {
		status = "all"
	}
	listings, err := getListings(status)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if listings == nil {
		listings = []Listing{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(listings)
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
	db, err = sql.Open("sqlite", dbPath)
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	// Enable WAL mode for concurrency
	db.Exec("PRAGMA journal_mode=WAL")
	db.Exec("PRAGMA busy_timeout=5000")

	// Verify DB connectivity
	if err := db.Ping(); err != nil {
		log.Fatalf("Database ping failed: %v", err)
	}
	log.Printf("✅ Connected to database: %s", dbPath)

	// Parse templates
	templates = template.Must(template.ParseFS(content, "web/templates/go/*.html"))
	log.Printf("✅ Templates loaded")

	mux := http.NewServeMux()

	// Static files
	staticFS := http.FileServer(http.FS(content))
	mux.Handle("GET /static/", staticFS)
	mux.Handle("GET /pwa/", staticFS)

	// Dashboard CSS (served at root for template compatibility)
	mux.HandleFunc("GET /dashboard.css", func(w http.ResponseWriter, r *http.Request) {
		data, err := content.ReadFile("web/static/dashboard.css")
		if err != nil {
			http.Error(w, "Not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "text/css")
		w.Write(data)
	})

	// Auth routes
	mux.HandleFunc("GET /login", handleLogin)
	mux.HandleFunc("POST /api/auth/login", handleLoginPost)
	mux.Handle("POST /logout", http.HandlerFunc(handleLogout))
	mux.Handle("GET /logout", http.HandlerFunc(handleLogout))

	// Dashboard
	mux.HandleFunc("GET /", handleDashboard)

	// API
	mux.HandleFunc("GET /api/listings", handleAPIListings)

	log.Printf("🚀 RealAgent starting on :%s", port)
	log.Printf("   Open http://localhost:%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
