package poi

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"net/url"
	"strings"
	"time"

	"realagent/internal/database"
)

// ─── Config ─────────────────────────────────────────────────────────

const (
	defaultRadius    = 500
	defaultTimeout   = 15 * time.Second  // per-HTTP-call; connection-refused is instant, slow mirrors timeout fast
	maxRetries       = 3
	baseRetryDelay   = 2 * time.Second
	interQueryDelay  = 1 * time.Second   // between batch groups to avoid rate-limiting
	categoryCap      = 10
)

// ─── Types ──────────────────────────────────────────────────────────

// CategoryDef defines a POI category and its Overpass query parameters.
type CategoryDef struct {
	Key     string
	Query   string // Overpass QL filter, e.g. '["amenity"="school"]'
	MaxPois int
}

// POIFetcher fetches points of interest from the Overpass API.
// Falls back through multiple mirrors if the primary is unreachable.
type POIFetcher struct {
	HTTPClient  *http.Client
	BaseURLs    []string // tried in order; first to connect wins
	MaxPerGroup int
	Verbose     bool
	MaxRetries  int
	BaseDelay   time.Duration
	QueryDelay  time.Duration
	Categories  []CategoryDef
}

// POIResult holds a single POI result.
type POIResult struct {
	Name     string  `json:"name"`
	Lat      float64 `json:"lat"`
	Lng      float64 `json:"lng"`
	Category string  `json:"category"`
	Type     string  `json:"type,omitempty"`
	Address  string  `json:"address,omitempty"`
}

// FetchResult holds all POI results for a location.
type FetchResult struct {
	Results    map[string][]POIResult `json:"results"`
	TotalPOIs  int                    `json:"total_pois"`
	Categories map[string]int         `json:"categories"`
	Radius     int                    `json:"radius"`
}

// ─── Overpass Response Types ───────────────────────────────────────

type overpassResponse struct {
	Elements []overpassElement `json:"elements"`
}

type overpassElement struct {
	Type   string            `json:"type"`
	ID     int64             `json:"id"`
	Lat    float64           `json:"lat,omitempty"`
	Lon    float64           `json:"lon,omitempty"`
	Center *overpassCenter   `json:"center,omitempty"`
	Tags   map[string]string `json:"tags"`
}

type overpassCenter struct {
	Lat float64 `json:"lat"`
	Lon float64 `json:"lon"`
}

// ─── Constructor ───────────────────────────────────────────────────

// fallbackURLs are tried in order.
// overpass-api.de is often blocked from certain networks;
// kumi.systems is a community mirror that's usually reachable.
var fallbackURLs = []string{
	"https://overpass.kumi.systems/api/interpreter", // working mirror (confirmed)
	"https://overpass-api.de/api/interpreter",       // primary, may be blocked
}

// New creates a POIFetcher with default categories and lazy background fetching.
func New() *POIFetcher {
	return &POIFetcher{
		HTTPClient:  &http.Client{Timeout: defaultTimeout},
		BaseURLs:    fallbackURLs,
		MaxPerGroup: 15,
		Verbose:     true,
		MaxRetries:  maxRetries,
		BaseDelay:   baseRetryDelay,
		QueryDelay:  interQueryDelay,
		Categories:  defaultCategories(),
	}
}

func defaultCategories() []CategoryDef {
	return []CategoryDef{
		{Key: "kindergartens", Query: `["amenity"="kindergarten"]`, MaxPois: categoryCap},
		{Key: "schools", Query: `["amenity"="school"]`, MaxPois: categoryCap},
		{Key: "lyceums", Query: `["amenity"="college"]`, MaxPois: categoryCap},
		{Key: "universities", Query: `["amenity"="university"]`, MaxPois: categoryCap},
		{Key: "hospitals", Query: `["amenity"="hospital"]`, MaxPois: categoryCap},
		{Key: "pharmacies", Query: `["amenity"="pharmacy"]`, MaxPois: categoryCap},
		{Key: "supermarkets", Query: `["shop"="supermarket"]`, MaxPois: categoryCap},
		{Key: "restaurants", Query: `["amenity"="restaurant"]`, MaxPois: categoryCap},
		{Key: "cafes", Query: `["amenity"="cafe"]`, MaxPois: categoryCap},
		{Key: "banks", Query: `["amenity"="bank"]`, MaxPois: categoryCap},
		{Key: "parks", Query: `["leisure"="park"]`, MaxPois: categoryCap},
		{Key: "parkings", Query: `["amenity"="parking"]`, MaxPois: categoryCap},
		{Key: "gyms", Query: `["leisure"="fitness_centre"]`, MaxPois: categoryCap},
		{Key: "cinemas", Query: `["amenity"="cinema"]`, MaxPois: categoryCap},
		{Key: "bus_stops", Query: `["highway"="bus_stop"]`, MaxPois: categoryCap},
		{Key: "police", Query: `["amenity"="police"]`, MaxPois: categoryCap},
		{Key: "post_offices", Query: `["amenity"="post_office"]`, MaxPois: categoryCap},
		{Key: "libraries", Query: `["amenity"="library"]`, MaxPois: categoryCap},
	}
}

// ─── Helpers ───────────────────────────────────────────────────────

func jitter(d time.Duration) time.Duration {
	// ±25% jitter
	frac := 0.75 + rand.Float64()*0.5
	return time.Duration(float64(d) * frac)
}

// ─── Combined (batch) queries ──────────────────────────────────────

// queryGroups defines how individual categories are merged into combined
// Overpass queries. Reduces 18 sequential requests to ~6 batched requests.
var queryGroups = [][]string{
	{"kindergartens", "schools", "lyceums", "universities"},
	{"hospitals", "pharmacies"},
	{"supermarkets"},
	{"restaurants", "cafes"},
	{"banks", "post_offices", "libraries", "police"},
	{"parks", "gyms", "cinemas"},
	{"parkings", "bus_stops"},
}

func (f *POIFetcher) buildBatchQuery(catKeys []string, lat, lng float64, radius int) string {
	var b strings.Builder
	b.WriteString("[out:json][timeout:30];(\n")
	for _, key := range catKeys {
		for _, cat := range f.Categories {
			if cat.Key == key {
				q := cat.Query // e.g. ["amenity"="school"]
				b.WriteString(fmt.Sprintf("  node%s(around:%d,%f,%f);\n", q, radius, lat, lng))
				b.WriteString(fmt.Sprintf("  way%s(around:%d,%f,%f);\n", q, radius, lat, lng))
				b.WriteString(fmt.Sprintf("  rel%s(around:%d,%f,%f);\n", q, radius, lat, lng))
				break
			}
		}
	}
	totalCap := 0
	for _, key := range catKeys {
		for _, cat := range f.Categories {
			if cat.Key == key {
				totalCap += cat.MaxPois
				break
			}
		}
	}
	b.WriteString(fmt.Sprintf(");out center %d;", totalCap+10))
	return b.String()
}

// classifyElement maps an Overpass element back to a category key based on tags.
func classifyElement(el overpassElement, catKeys []string) string {
	t := el.Tags
	amenity := t["amenity"]
	shop := t["shop"]
	leisure := t["leisure"]
	highway := t["highway"]

	for _, key := range catKeys {
		switch key {
		case "kindergartens":
			if amenity == "kindergarten" || amenity == "childcare" {
				return key
			}
		case "schools":
			if amenity == "school" {
				return key
			}
		case "lyceums":
			if amenity == "college" {
				return key
			}
		case "universities":
			if amenity == "university" {
				return key
			}
		case "hospitals":
			if amenity == "hospital" || amenity == "clinic" || amenity == "doctors" || amenity == "dentist" {
				return key
			}
		case "pharmacies":
			if amenity == "pharmacy" || shop == "chemist" {
				return key
			}
		case "supermarkets":
			if shop == "supermarket" || shop == "convenience" || shop == "grocery" {
				return key
			}
		case "restaurants":
			if amenity == "restaurant" || amenity == "fast_food" {
				return key
			}
		case "cafes":
			if amenity == "cafe" || amenity == "bar" || amenity == "pub" {
				return key
			}
		case "banks":
			if amenity == "bank" {
				return key
			}
		case "parks":
			if leisure == "park" {
				return key
			}
		case "parkings":
			if amenity == "parking" {
				return key
			}
		case "gyms":
			if leisure == "fitness_centre" || leisure == "sports_centre" || amenity == "gym" {
				return key
			}
		case "cinemas":
			if amenity == "cinema" || amenity == "theatre" {
				return key
			}
		case "bus_stops":
			if highway == "bus_stop" {
				return key
			}
		case "police":
			if amenity == "police" {
				return key
			}
		case "post_offices":
			if amenity == "post_office" {
				return key
			}
		case "libraries":
			if amenity == "library" {
				return key
			}
		}
	}
	return ""
}

// ─── Fetching ──────────────────────────────────────────────────────

// FetchAll fetches POIs for all categories at the given location using
// batched Overpass queries with retry+backoff and inter-query delays
// to avoid throttling the API.
func (f *POIFetcher) FetchAll(lat, lng float64, radius int) (*FetchResult, error) {
	result := &FetchResult{
		Results:    make(map[string][]POIResult),
		Categories: make(map[string]int),
		Radius:     radius,
	}

	if radius <= 0 {
		radius = defaultRadius
	}

	for _, group := range queryGroups {
		// Inter-query delay to avoid hammering Overpass
		time.Sleep(jitter(f.QueryDelay))

		pois, err := f.fetchBatch(lat, lng, radius, group)
		if err != nil {
			if f.Verbose {
				fmt.Printf("  ⚠️ POI batch %v failed\n", group)
			}
			continue
		}

		for catKey, catPOIs := range pois {
			if len(catPOIs) > 0 {
				// Find the cap for this category
				cap := categoryCap
				for _, cat := range f.Categories {
					if cat.Key == catKey {
						cap = cat.MaxPois
						break
					}
				}
				if len(catPOIs) > cap {
					catPOIs = catPOIs[:cap]
				}
				result.Results[catKey] = catPOIs
				result.Categories[catKey] = len(catPOIs)
				result.TotalPOIs += len(catPOIs)
			}
		}
	}

	return result, nil
}

// fetchBatch executes a single combined Overpass query for a group of
// categories, with retry + exponential backoff + jitter + multi-mirror fallback.
// Only prints one line per batch on success or final failure.
func (f *POIFetcher) fetchBatch(lat, lng float64, radius int, catKeys []string) (map[string][]POIResult, error) {
	query := f.buildBatchQuery(catKeys, lat, lng, radius)

	if f.Verbose {
		log.Printf("  POI batch %v", catKeys)
	}

	var lastErr error
	for attempt := 0; attempt < f.MaxRetries; attempt++ {
		if attempt > 0 {
			delay := jitter(f.BaseDelay * (1 << attempt))
			time.Sleep(delay)
		}

		raw, err := f.doRequestWithFallback(query)
		if err != nil {
			lastErr = err
			continue
		}

		var overpass overpassResponse
		if err := json.Unmarshal(raw, &overpass); err != nil {
			lastErr = fmt.Errorf("parse: %w", err)
			continue
		}

		// Categorize elements
		catResults := make(map[string][]overpassElement)
		for _, el := range overpass.Elements {
			assigned := classifyElement(el, catKeys)
			if assigned != "" {
				catResults[assigned] = append(catResults[assigned], el)
			}
		}

		// Convert to POIResults
		results := make(map[string][]POIResult)
		for _, key := range catKeys {
			elements := catResults[key]
			if len(elements) == 0 {
				continue
			}
			var pois []POIResult
			for _, el := range elements {
				poi := elementToPOI(el, key)
				if poi != nil {
					pois = append(pois, *poi)
				}
			}
			if len(pois) > 0 {
				results[key] = pois
			}
		}

		if f.Verbose {
			total := 0
			for _, v := range results {
				total += len(v)
			}
			log.Printf("  POI batch %v: %d POIs", catKeys, total)
		}
		return results, nil
	}

	if f.Verbose {
		log.Printf("  ⚠️ POI batch %v failed after %d retries: %v", catKeys, f.MaxRetries, lastErr)
	}
	return nil, lastErr
}

// doRequestWithFallback tries each BaseURL in order until one succeeds.
// Connection-refused errors skip to the next mirror immediately.
func (f *POIFetcher) doRequestWithFallback(query string) ([]byte, error) {
	var lastErr error
	for i, base := range f.BaseURLs {
		u := base + "?data=" + url.QueryEscape(query)

		raw, err := f.doRequest(u)
		if err == nil {
			if f.Verbose && i > 0 {
				log.Printf("  (connected via fallback: %s)", base)
			}
			return raw, nil
		}

		lastErr = err
		// Connection-level errors (DNS / refused / timeout) → try next mirror
		var urlErr *url.Error
		if errors.As(err, &urlErr) {
			continue
		}
		// Non-connection errors (rate limit, parse, etc.) → don't fallback
		return nil, err
	}
	return nil, fmt.Errorf("all mirrors failed: %w", lastErr)
}

func (f *POIFetcher) doRequest(url string) ([]byte, error) {
	resp, err := f.HTTPClient.Get(url)
	if err != nil {
		return nil, err // already *url.Error from stdlib
	}
	defer resp.Body.Close()

	if resp.StatusCode == 429 {
		return nil, fmt.Errorf("rate limited (429)")
	}
	if resp.StatusCode == 504 {
		return nil, fmt.Errorf("gateway timeout (504)")
	}
	if resp.StatusCode >= 500 {
		return nil, fmt.Errorf("server error (%d)", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read: %w", err)
	}
	return body, nil
}

func elementToPOI(el overpassElement, catKey string) *POIResult {
	name := el.Tags["name"]
	if name == "" {
		name = el.Tags["brand"]
	}
	if name == "" {
		name = el.Tags["amenity"]
		if name == "" {
			name = el.Tags["shop"]
		}
		if name == "" {
			name = el.Tags["leisure"]
		}
		if name == "" {
			name = el.Tags["highway"]
		}
		if name == "" {
			return nil
		}
	}

	poiLat := el.Lat
	poiLng := el.Lon
	if poiLat == 0 && el.Center != nil {
		poiLat = el.Center.Lat
		poiLng = el.Center.Lon
	}

	addr := strings.TrimSpace(el.Tags["addr:street"] + " " + el.Tags["addr:housenumber"])

	return &POIResult{
		Name:     name,
		Lat:      poiLat,
		Lng:      poiLng,
		Category: catKey,
		Type:     el.Tags["amenity"],
		Address:  addr,
	}
}

// ─── Convert to DB format ─────────────────────────────────────────

// ToDBMap converts FetchResult to the map format expected by database.SavePOIData.
func (fr *FetchResult) ToDBMap() map[string][]interface{} {
	result := make(map[string][]interface{})
	for cat, pois := range fr.Results {
		items := make([]interface{}, len(pois))
		for i, p := range pois {
			items[i] = map[string]interface{}{
				"name": p.Name,
				"lat":  p.Lat,
				"lng":  p.Lng,
				"type": p.Type,
			}
		}
		result[cat] = items
	}
	return result
}

// ─── Convenience ──────────────────────────────────────────────────

// FetchAndSave fetches POIs and saves them to the database in one call.
func FetchAndSave(db *sql.DB, listingID string, lat, lng float64, radius int) (*FetchResult, error) {
	f := New()
	result, err := f.FetchAll(lat, lng, radius)
	if err != nil {
		return nil, err
	}

	poiMap := result.ToDBMap()
	if err := database.SavePOIData(db, listingID, poiMap, radius); err != nil {
		return nil, fmt.Errorf("save: %w", err)
	}

	return result, nil
}
