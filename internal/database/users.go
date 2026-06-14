package database

import (
	"database/sql"
	"fmt"
	"time"
)

// ─── Types ──────────────────────────────────────────────────────────

type User struct {
	ID           int    `json:"id"`
	Username     string `json:"username"`
	PasswordHash string `json:"-"`
	FullName     string `json:"full_name"`
	Role         string `json:"role"`
	Active       bool   `json:"active"`
	CreatedAt    string `json:"created_at"`
	LastLogin    string `json:"last_login"`
}

// ─── Auth ──────────────────────────────────────────────────────────

// AuthenticateUser verifies credentials and returns user info.
func AuthenticateUser(db *sql.DB, username, password string) (*User, error) {
	hash := sha256Hex(password)

	var u User
	var active int
	err := db.QueryRow(`SELECT id, username, full_name, role, active
		FROM users WHERE username = ? AND password_hash = ?`,
		username, hash).Scan(&u.ID, &u.Username, &u.FullName, &u.Role, &active)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("invalid credentials")
	}
	if err != nil {
		return nil, err
	}
	if active != 1 {
		return nil, fmt.Errorf("account disabled")
	}
	u.Active = true

	// Update last login
	now := time.Now().UTC().Format(time.RFC3339)
	db.Exec("UPDATE users SET last_login = ? WHERE id = ?", now, u.ID)

	return &u, nil
}

// ─── CRUD ──────────────────────────────────────────────────────────

// GetUsers returns all users.
func GetUsers(db *sql.DB) ([]User, error) {
	rows, err := db.Query(`SELECT id, username, full_name, role, active, created_at, last_login
		FROM users ORDER BY username`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []User
	for rows.Next() {
		var u User
		var active int
		var lastLogin sql.NullString
		rows.Scan(&u.ID, &u.Username, &u.FullName, &u.Role, &active, &u.CreatedAt, &lastLogin)
		u.Active = active == 1
		if lastLogin.Valid {
			u.LastLogin = lastLogin.String
		}
		users = append(users, u)
	}
	return users, nil
}

// GetUser returns a single user by ID.
func GetUser(db *sql.DB, userID int) (*User, error) {
	var u User
	var active int
	err := db.QueryRow(`SELECT id, username, full_name, role, active, created_at, last_login
		FROM users WHERE id = ?`, userID).Scan(&u.ID, &u.Username, &u.FullName, &u.Role, &active, &u.CreatedAt, &u.LastLogin)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	u.Active = active == 1
	return &u, nil
}

// CreateUser creates a new user.
func CreateUser(db *sql.DB, username, password, fullName, role string) (*User, error) {
	hash := sha256Hex(password)
	if role == "" {
		role = "agent"
	}
	result, err := db.Exec(`INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)`,
		username, hash, fullName, role)
	if err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}
	id, _ := result.LastInsertId()
	return GetUser(db, int(id))
}

// UpdateUserPassword updates a user's password.
func UpdateUserPassword(db *sql.DB, userID int, newPassword string) error {
	hash := sha256Hex(newPassword)
	_, err := db.Exec("UPDATE users SET password_hash = ? WHERE id = ?", hash, userID)
	return err
}

// DeleteUser deletes a user by ID.
func DeleteUser(db *sql.DB, userID int) error {
	_, err := db.Exec("DELETE FROM users WHERE id = ?", userID)
	return err
}
