package poi

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"realagent/internal/database"
)

// ─── Types ──────────────────────────────────────────────────────────

// CategoryDef defines a POI category and its Overpass query parameters.
type CategoryDef struct {
	Key     string
	Query   string // Overpass QL filter, e.g. '["amenity"="school"]'
	MaxPois int
}

// POIFetcher fetches points of interest from the Overpass API.
type POIFetcher struct {
	HTTPClient  *http.Client
	BaseURL     string
	MaxPerGroup int
	Verbose     bool
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

// New creates a POIFetcher with default categories.
func New() *POIFetcher {
	return &POIFetcher{
		HTTPClient:  &http.Client{Timeout: 30 * time.Second},
		BaseURL:     "https://overpass-api.de/api/interpreter",
		MaxPerGroup: 15,
		Categories:  defaultCategories(),
	}
}

func defaultCategories() []CategoryDef {
	return []CategoryDef{
		{Key: "kindergartens", Query: `["amenity"="kindergarten"]`, MaxPois: 5},
		{Key: "schools", Query: `["amenity"="school"]`, MaxPois: 5},
		{Key: "lyceums", Query: `["amenity"="college"]`, MaxPois: 5},
		{Key: "universities", Query: `["amenity"="university"]`, MaxPois: 5},
		{Key: "hospitals", Query: `["amenity"="hospital"]`, MaxPois: 5},
		{Key: "pharmacies", Query: `["amenity"="pharmacy"]`, MaxPois: 5},
		{Key: "supermarkets", Query: `["shop"="supermarket"]`, MaxPois: 5},
		{Key: "restaurants", Query: `["amenity"="restaurant"]`, MaxPois: 10},
		{Key: "cafes", Query: `["amenity"="cafe"]`, MaxPois: 5},
		{Key: "banks", Query: `["amenity"="bank"]`, MaxPois: 5},
		{Key: "parks", Query: `["leisure"="park"]`, MaxPois: 5},
		{Key: "parkings", Query: `["amenity"="parking"]`, MaxPois: 5},
		{Key: "gyms", Query: `["leisure"="fitness_centre"]`, MaxPois: 5},
		{Key: "cinemas", Query: `["amenity"="cinema"]`, MaxPois: 3},
		{Key: "bus_stops", Query: `["highway"="bus_stop"]`, MaxPois: 10},
		{Key: "police", Query: `["amenity"="police"]`, MaxPois: 3},
		{Key: "post_offices", Query: `["amenity"="post_office"]`, MaxPois: 3},
		{Key: "libraries", Query: `["amenity"="library"]`, MaxPois: 3},
	}
}

// ─── Fetching ──────────────────────────────────────────────────────

// FetchAll fetches POIs for all categories at the given location.
func (f *POIFetcher) FetchAll(lat, lng float64, radius int) (*FetchResult, error) {
	result := &FetchResult{
		Results:    make(map[string][]POIResult),
		Categories: make(map[string]int),
		Radius:     radius,
	}

	if radius <= 0 {
		radius = 500
	}

	for _, cat := range f.Categories {
		pois, err := f.fetchCategory(lat, lng, radius, cat)
		if err != nil {
			if f.Verbose {
				fmt.Printf("  ⚠️ POI fetch error for %s: %v\n", cat.Key, err)
			}
			continue
		}
		if len(pois) > 0 {
			if len(pois) > cat.MaxPois {
				pois = pois[:cat.MaxPois]
			}
			result.Results[cat.Key] = pois
			result.Categories[cat.Key] = len(pois)
			result.TotalPOIs += len(pois)
		}
	}

	return result, nil
}

func (f *POIFetcher) fetchCategory(lat, lng float64, radius int, cat CategoryDef) ([]POIResult, error) {
	bboxLat := float64(radius) * 0.009
	bboxLng := float64(radius) * 0.009
	if bboxLng > 0.5 {
		bboxLng = 0.5
	}

	overpassQ := fmt.Sprintf(`[out:json];(`+
		`node%s(%f,%f,%f,%f);`+
		`way%s(%f,%f,%f,%f);`+
		`rel%s(%f,%f,%f,%f);`+
		`);out center %d;`,
		cat.Query, lat-bboxLat, lng-bboxLng, lat+bboxLat, lng+bboxLng,
		cat.Query, lat-bboxLat, lng-bboxLng, lat+bboxLat, lng+bboxLng,
		cat.Query, lat-bboxLat, lng-bboxLng, lat+bboxLat, lng+bboxLng,
		cat.MaxPois+5)

	u := f.BaseURL + "?data=" + url.QueryEscape(overpassQ)

	resp, err := f.HTTPClient.Get(u)
	if err != nil {
		return nil, fmt.Errorf("http: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read: %w", err)
	}

	var overpass overpassResponse
	if err := json.Unmarshal(body, &overpass); err != nil {
		return nil, fmt.Errorf("parse: %w", err)
	}

	var pois []POIResult
	for _, el := range overpass.Elements {
		name := el.Tags["name"]
		if name == "" {
			name = el.Tags["brand"]
		}
		if name == "" {
			continue
		}

		poiLat := el.Lat
		poiLng := el.Lon
		if poiLat == 0 && el.Center != nil {
			poiLat = el.Center.Lat
			poiLng = el.Center.Lon
		}

		addr := strings.TrimSpace(
			el.Tags["addr:street"] + " " + el.Tags["addr:housenumber"])

		pois = append(pois, POIResult{
			Name:     name,
			Lat:      poiLat,
			Lng:      poiLng,
			Category: cat.Key,
			Type:     el.Tags["amenity"],
			Address:  addr,
		})
	}

	return pois, nil
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
