package database

import (
	"database/sql"
	"fmt"
	"time"
)

// ─── Types ──────────────────────────────────────────────────────────

type JournalEntry struct {
	ID        int    `json:"id"`
	ListingID string `json:"listing_id"`
	EntryType string `json:"entry_type"`
	Title     string `json:"title"`
	Content   string `json:"content"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
	User      string `json:"user"`
	Tags      string `json:"tags"`
}

// ─── CRUD ──────────────────────────────────────────────────────────

// GetJournalEntries returns journal entries with optional filters.
func GetJournalEntries(db *sql.DB, listingID, entryType string, limit, offset int) ([]JournalEntry, error) {
	where := []string{"1=1"}
	var args []interface{}

	if listingID != "" {
		where = append(where, "listing_id = ?")
		args = append(args, listingID)
	}
	if entryType != "" {
		where = append(where, "entry_type = ?")
		args = append(args, entryType)
	}
	if limit <= 0 {
		limit = 100
	}

	query := fmt.Sprintf(`SELECT id, listing_id, entry_type, title, content,
		created_at, updated_at, user, tags FROM journal_entries
		WHERE %s ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		joinStrings(where, " AND "))
	args = append(args, limit, offset)

	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []JournalEntry
	for rows.Next() {
		var e JournalEntry
		var listingID, content sql.NullString
		rows.Scan(&e.ID, &listingID, &e.EntryType, &e.Title, &content,
			&e.CreatedAt, &e.UpdatedAt, &e.User, &e.Tags)
		if listingID.Valid {
			e.ListingID = listingID.String
		}
		if content.Valid {
			e.Content = content.String
		}
		entries = append(entries, e)
	}
	return entries, nil
}

// CreateJournalEntry creates a new journal entry.
func CreateJournalEntry(db *sql.DB, listingID, entryType, title, content, user, tags string) (*JournalEntry, error) {
	now := time.Now().UTC().Format(time.RFC3339)
	var lid *string
	if listingID != "" {
		lid = &listingID
	}
	var eType string
	if entryType == "" {
		eType = "log"
	} else {
		eType = entryType
	}

	result, err := db.Exec(`INSERT INTO journal_entries
		(listing_id, entry_type, title, content, created_at, updated_at, user, tags)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		lid, eType, title, content, now, now, user, tags)
	if err != nil {
		return nil, fmt.Errorf("create journal: %w", err)
	}
	id, _ := result.LastInsertId()

	return GetJournalEntry(db, int(id))
}

// GetJournalEntry returns a single journal entry by ID.
func GetJournalEntry(db *sql.DB, entryID int) (*JournalEntry, error) {
	var e JournalEntry
	var listingID, content sql.NullString
	err := db.QueryRow(`SELECT id, listing_id, entry_type, title, content,
		created_at, updated_at, user, tags FROM journal_entries WHERE id = ?`,
		entryID).Scan(&e.ID, &listingID, &e.EntryType, &e.Title, &content,
		&e.CreatedAt, &e.UpdatedAt, &e.User, &e.Tags)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if listingID.Valid {
		e.ListingID = listingID.String
	}
	if content.Valid {
		e.Content = content.String
	}
	return &e, nil
}

// UpdateJournalEntry updates a journal entry's fields.
func UpdateJournalEntry(db *sql.DB, entryID int, title, content, entryType, tags *string) error {
	setClauses := []string{"updated_at = ?"}
	args := []interface{}{time.Now().UTC().Format(time.RFC3339)}

	if title != nil {
		setClauses = append(setClauses, "title = ?")
		args = append(args, *title)
	}
	if content != nil {
		setClauses = append(setClauses, "content = ?")
		args = append(args, *content)
	}
	if entryType != nil {
		setClauses = append(setClauses, "entry_type = ?")
		args = append(args, *entryType)
	}
	if tags != nil {
		setClauses = append(setClauses, "tags = ?")
		args = append(args, *tags)
	}
	args = append(args, entryID)

	query := fmt.Sprintf("UPDATE journal_entries SET %s WHERE id = ?",
		joinStrings(setClauses, ", "))
	_, err := db.Exec(query, args...)
	return err
}

// DeleteJournalEntry deletes a journal entry.
func DeleteJournalEntry(db *sql.DB, entryID int) error {
	_, err := db.Exec("DELETE FROM journal_entries WHERE id = ?", entryID)
	return err
}

// ClearJournalEntries clears entries older than the specified age ("1week", "1month", "all").
func ClearJournalEntries(db *sql.DB, age string) (int64, error) {
	var result sql.Result
	var err error
	switch age {
	case "1week":
		result, err = db.Exec("DELETE FROM journal_entries WHERE created_at < datetime('now', '-7 days')")
	case "1month":
		result, err = db.Exec("DELETE FROM journal_entries WHERE created_at < datetime('now', '-30 days')")
	default:
		result, err = db.Exec("DELETE FROM journal_entries")
	}
	if err != nil {
		return 0, err
	}
	n, _ := result.RowsAffected()
	return n, nil
}
