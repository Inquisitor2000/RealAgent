package scraper

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"

	"realagent/internal/database"
	"realagent/internal/poi"
)

// ─── Types ──────────────────────────────────────────────────────────

// ScrapeResult holds the outcome of scraping a single listing.
type ScrapeResult struct {
	Success   bool   `json:"success"`
	ListingID string `json:"listing_id"`
	URL       string `json:"url"`
	Error     string `json:"error,omitempty"`
}

// SyncStatus tracks the progress of a batch sync operation.
type SyncStatus struct {
	Running    bool      `json:"running"`
	Total      int       `json:"total"`
	Completed  int       `json:"completed"`
	Failed     int       `json:"failed"`
	StartedAt  time.Time `json:"started_at"`
	FinishedAt time.Time `json:"finished_at,omitempty"`
	Errors     []string  `json:"errors,omitempty"`
}

// BilingualData holds scraped content in both Romanian and Russian.
type BilingualData struct {
	RO struct {
		Title       string
		Description string
		Features    map[string]map[string]string
		Amenities   map[string]bool
		Address     string
		Price       map[string]string
		Contact     string
	}
	RU struct {
		Title       string
		Description string
		Features    map[string]map[string]string
		Amenities   map[string]bool
		Address     string
		Price       map[string]string
		Contact     string
	}
	SourceLang string // "ro" or "ru"
}

// Scraper orchestrates the full listing scrape flow.
type Scraper struct {
	Client      *http.Client
	DB          *sql.DB
	ListingsDir string

	mu       sync.Mutex
	cancel   context.CancelFunc
	status   SyncStatus
}

// New creates a new Scraper.
func New(client *http.Client, db *sql.DB, listingsDir string) *Scraper {
	if client == nil {
		client = &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        20,
				IdleConnTimeout:     30 * time.Second,
				DisableCompression:  false,
			},
		}
	}
	return &Scraper{
		Client:      client,
		DB:          db,
		ListingsDir: listingsDir,
	}
}

// ─── Public API ─────────────────────────────────────────────────────

// ScrapeListing performs the full scrape for a single URL.
func (s *Scraper) ScrapeListing(ctx context.Context, urlStr, templateName string) (*ScrapeResult, error) {
	id := extractListingID(urlStr)
	if id == "" {
		return &ScrapeResult{URL: urlStr, Error: "could not extract listing ID from URL"}, nil
	}

	log.Printf("🔍 Scraping: %s (id=%s)", urlStr, id)

	// 1. Fetch HTML
	html, err := s.fetchHTML(ctx, urlStr)
	if err != nil {
		return &ScrapeResult{ListingID: id, URL: urlStr, Error: fmt.Sprintf("fetch failed: %v", err)}, nil
	}

	// 2. Parse structured data
	scraped, err := ParseHTML(html)
	if err != nil {
		return &ScrapeResult{ListingID: id, URL: urlStr, Error: fmt.Sprintf("parse failed: %v", err)}, nil
	}
	log.Printf("  Parsed: title=%q desc=%dch price=%d currencies images=%d features=%d address=%q",
		truncStr(scraped.Title, 40),
		len(scraped.Description),
		len(scraped.PriceMap),
		len(scraped.Images),
		len(scraped.Features),
		scraped.Address)

	// 3. Extract phone from raw HTML
	phone := ExtractPhone(html)
	if phone != "" && phone != "N/A" {
		scraped.Phone = phone
	}

	// 4. Determine source language
	sourceLang := detectLanguage(urlStr)
	log.Printf("  Source language: %s", sourceLang)
	scraped.SourceLang = sourceLang

	// 5. For 999.md, scrape bilingual content
	var bilingual *BilingualData
	if is999md(urlStr) {
		bilingual, err = s.scrapeBilingual(ctx, urlStr, html, sourceLang)
		if err != nil {
			log.Printf("  ⚠️ Bilingual scrape partial: %v", err)
		}
	} else {
		bilingual = buildSingleLanguage(scraped, sourceLang)
	}

	// 6. Download images
	localImages, err := s.downloadImages(ctx, scraped.Images, id)
	if err != nil {
		log.Printf("  ⚠️ Image download partial: %v", err)
	}
	if localImages == nil {
		localImages = []string{}
	}

	// 7. Geocode address
	lat, lng, mapTitle := s.geocodeListing(ctx, scraped, id)

	// 8. Build listing data for DB
	listingData := s.buildListingData(id, urlStr, scraped, bilingual, localImages, lat, lng, mapTitle, templateName)

	// 9. Save to database
	savedID, err := database.InsertListing(s.DB, listingData)
	if err != nil {
		return &ScrapeResult{ListingID: id, URL: urlStr, Error: fmt.Sprintf("db save failed: %v", err)}, nil
	}

	// 10. Fetch POI data in background — listing returned immediately,
	//     POIs populate in DB as they arrive.
	if lat != 0 || lng != 0 {
		savedID := savedID // capture range var
		go func() {
			if _, err := poi.FetchAndSave(s.DB, savedID, lat, lng, 500); err != nil {
				log.Printf("⚠️ POI fetch after scrape failed for %s: %v", savedID, err)
			} else {
				log.Printf("  POI data fetched for %s", savedID)
			}
		}()
	}

	log.Printf("✅ Saved: %s (POI fetching in background)", savedID)
	return &ScrapeResult{Success: true, ListingID: savedID, URL: urlStr}, nil
}

// ScrapeMultiple scrapes multiple URLs concurrently with a worker pool.
func (s *Scraper) ScrapeMultiple(ctx context.Context, urls []string, templateName string, workers int) <-chan ScrapeResult {
	results := make(chan ScrapeResult, len(urls))
	if workers <= 0 {
		workers = 4
	}

	go func() {
		defer close(results)

		sem := make(chan struct{}, workers)
		var wg sync.WaitGroup

		for _, u := range urls {
			wg.Add(1)
			sem <- struct{}{}

			go func(urlStr string) {
				defer wg.Done()
				defer func() { <-sem }()

				result, err := s.ScrapeListing(ctx, urlStr, templateName)
				if err != nil {
					results <- ScrapeResult{URL: urlStr, Error: err.Error()}
					return
				}
				results <- *result
			}(u)
		}

		wg.Wait()
	}()

	return results
}

// ─── Batch Sync ─────────────────────────────────────────────────────

// StartSync begins a batch sync in a background goroutine.
func (s *Scraper) StartSync(ctx context.Context, urls []string, templateName string) error {
	s.mu.Lock()
	if s.status.Running {
		s.mu.Unlock()
		return fmt.Errorf("sync already running")
	}
	ctx, cancel := context.WithCancel(ctx)
	s.cancel = cancel
	s.status = SyncStatus{
		Running:   true,
		Total:     len(urls),
		StartedAt: time.Now(),
	}
	s.mu.Unlock()

	go func() {
		results := s.ScrapeMultiple(ctx, urls, templateName, 4)
		for res := range results {
			s.mu.Lock()
			if res.Success {
				s.status.Completed++
			} else {
				s.status.Failed++
				if len(s.status.Errors) < 100 {
					s.status.Errors = append(s.status.Errors, fmt.Sprintf("%s: %s", res.URL, res.Error))
				}
			}
			s.mu.Unlock()
		}
		s.mu.Lock()
		s.status.Running = false
		s.status.FinishedAt = time.Now()
		s.mu.Unlock()
	}()

	return nil
}

// StopSync cancels the ongoing sync operation.
func (s *Scraper) StopSync() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cancel != nil {
		s.cancel()
	}
	s.status.Running = false
}

// GetSyncStatus returns the current sync status.
func (s *Scraper) GetSyncStatus() SyncStatus {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.status
}

// ─── Internal: HTML Fetching ────────────────────────────────────────

func (s *Scraper) fetchHTML(ctx context.Context, urlStr string) (string, error) {
	var lastErr error

	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(500*(1<<attempt)) * time.Millisecond
			jitter := time.Duration(rand.Intn(200)) * time.Millisecond
			select {
			case <-ctx.Done():
				return "", ctx.Err()
			case <-time.After(backoff + jitter):
			}
		}

		req, err := http.NewRequestWithContext(ctx, "GET", urlStr, nil)
		if err != nil {
			return "", fmt.Errorf("create request: %w", err)
		}

		req.Header.Set("User-Agent", userAgents[rand.Intn(len(userAgents))])
		req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
		req.Header.Set("Accept-Language", "en-US,en;q=0.5")

		resp, err := s.Client.Do(req)
		if err != nil {
			lastErr = err
			log.Printf("  Attempt %d failed: %v", attempt+1, err)
			continue
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			lastErr = fmt.Errorf("read body: %w", err)
			continue
		}

		if resp.StatusCode != 200 {
			lastErr = fmt.Errorf("HTTP %d", resp.StatusCode)
			continue
		}

		return string(body), nil
	}

	return "", fmt.Errorf("all retries failed: %w", lastErr)
}

// ─── Internal: Bilingual Scraping ────────────────────────────────────

func (s *Scraper) scrapeBilingual(ctx context.Context, urlStr, primaryHTML, sourceLang string) (*BilingualData, error) {
	bilingual := &BilingualData{SourceLang: sourceLang}

	// Determine the alternate language URL
	var altURL string
	if strings.Contains(urlStr, "/ro/") {
		altURL = strings.Replace(urlStr, "/ro/", "/ru/", 1)
		sourceLang = "ro"
	} else if strings.Contains(urlStr, "/ru/") {
		altURL = strings.Replace(urlStr, "/ru/", "/ro/", 1)
		sourceLang = "ru"
	} else {
		// No language in URL, try both
		parsed, _ := url.Parse(urlStr)
		base := strings.TrimSuffix(urlStr, parsed.Path)
		altURL = base + "/ro" + parsed.Path
	}

	// Parse primary (already have HTML)
	primary, err := ParseHTML(primaryHTML)
	if err != nil {
		return nil, fmt.Errorf("parse primary: %w", err)
	}
	primaryPhone := ExtractPhone(primaryHTML)

	// Fill primary language
	if sourceLang == "ro" {
		bilingual.RO.Title = primary.Title
		bilingual.RO.Description = primary.Description
		bilingual.RO.Features = primary.Features
		bilingual.RO.Amenities = primary.Amenities
		bilingual.RO.Price = primary.PriceMap
		bilingual.RO.Contact = primaryPhone
	} else {
		bilingual.RU.Title = primary.Title
		bilingual.RU.Description = primary.Description
		bilingual.RU.Features = primary.Features
		bilingual.RU.Amenities = primary.Amenities
		bilingual.RU.Price = primary.PriceMap
		bilingual.RU.Contact = primaryPhone
	}

	// Scrape alternate language
	altHTML, err := s.fetchHTML(ctx, altURL)
	if err != nil {
		log.Printf("  ⚠️ Alternate language fetch failed: %v", err)
		// Fill alternate with translation of primary
		s.fillAlternateFromTranslation(bilingual, sourceLang)
		return bilingual, nil
	}

	alt, err := ParseHTML(altHTML)
	if err != nil {
		log.Printf("  ⚠️ Alternate language parse failed: %v", err)
		s.fillAlternateFromTranslation(bilingual, sourceLang)
		return bilingual, nil
	}
	altPhone := ExtractPhone(altHTML)

	// Fill alternate language
	if sourceLang == "ro" {
		bilingual.RU.Title = alt.Title
		bilingual.RU.Description = alt.Description
		bilingual.RU.Features = alt.Features
		bilingual.RU.Amenities = alt.Amenities
		bilingual.RU.Price = alt.PriceMap
		bilingual.RU.Contact = altPhone
	} else {
		bilingual.RO.Title = alt.Title
		bilingual.RO.Description = alt.Description
		bilingual.RO.Features = alt.Features
		bilingual.RO.Amenities = alt.Amenities
		bilingual.RO.Price = alt.PriceMap
		bilingual.RO.Contact = altPhone
	}

	// Use primary phone if alternate didn't get one
	if sourceLang == "ro" && bilingual.RU.Contact == "" || bilingual.RU.Contact == "N/A" {
		bilingual.RU.Contact = bilingual.RO.Contact
	} else if sourceLang == "ru" && (bilingual.RO.Contact == "" || bilingual.RO.Contact == "N/A") {
		bilingual.RO.Contact = bilingual.RU.Contact
	}

	// Parse primary address and use for both
	if primary.Address != "" && primary.Address != "N/A" {
		bilingual.RO.Address = primary.Address
		bilingual.RU.Address = primary.Address
	}

	return bilingual, nil
}

func (s *Scraper) fillAlternateFromTranslation(bilingual *BilingualData, sourceLang string) {
	// Use translator.go to fill alternate language via translation
	var srcTitle, srcDesc string
	var srcFeatures map[string]map[string]string
	var srcAmenities map[string]bool

	if sourceLang == "ro" {
		srcTitle = bilingual.RO.Title
		srcDesc = bilingual.RO.Description
		srcFeatures = bilingual.RO.Features
		srcAmenities = bilingual.RO.Amenities
	} else {
		srcTitle = bilingual.RU.Title
		srcDesc = bilingual.RU.Description
		srcFeatures = bilingual.RU.Features
		srcAmenities = bilingual.RU.Amenities
	}

	translatedFeatures := make(map[string]map[string]string)
	for section, items := range srcFeatures {
		translatedSection := TranslateFeature(section, sourceLang == "ru")
		translatedItems := make(map[string]string)
		for k, v := range items {
			tk := TranslateFeature(k, sourceLang == "ru")
			tv := TranslateFeature(v, sourceLang == "ru")
			translatedItems[tk] = tv
		}
		translatedFeatures[translatedSection] = translatedItems
	}

	if sourceLang == "ro" {
		bilingual.RU.Title = TranslateRussianToRomanian(srcTitle)
		bilingual.RU.Description = srcDesc // keep same desc
		bilingual.RU.Features = translatedFeatures
		bilingual.RU.Amenities = srcAmenities
		bilingual.RU.Price = bilingual.RO.Price
		bilingual.RU.Contact = bilingual.RO.Contact
	} else {
		bilingual.RO.Title = TranslateRussianToRomanian(srcTitle)
		bilingual.RO.Description = srcDesc
		bilingual.RO.Features = translatedFeatures
		bilingual.RO.Amenities = srcAmenities
		bilingual.RO.Price = bilingual.RU.Price
		bilingual.RO.Contact = bilingual.RU.Contact
	}
}

func buildSingleLanguage(scraped *ScrapedData, lang string) *BilingualData {
	b := &BilingualData{SourceLang: lang}
	if lang == "ro" {
		b.RO.Title = scraped.Title
		b.RO.Description = scraped.Description
		b.RO.Features = scraped.Features
		b.RO.Amenities = scraped.Amenities
		b.RO.Price = scraped.PriceMap
		b.RO.Address = scraped.Address
		b.RU.Title = TranslateRussianToRomanian(scraped.Title)
		b.RU.Description = scraped.Description
		b.RU.Features = translateFeatureMap(scraped.Features, true)
		b.RU.Amenities = scraped.Amenities
		b.RU.Price = scraped.PriceMap
	} else {
		b.RU.Title = scraped.Title
		b.RU.Description = scraped.Description
		b.RU.Features = scraped.Features
		b.RU.Amenities = scraped.Amenities
		b.RU.Price = scraped.PriceMap
		b.RU.Address = scraped.Address
		b.RO.Title = TranslateRussianToRomanian(scraped.Title)
		b.RO.Description = scraped.Description
		b.RO.Features = translateFeatureMap(scraped.Features, false)
		b.RO.Amenities = scraped.Amenities
		b.RO.Price = scraped.PriceMap
	}
	return b
}

func translateFeatureMap(features map[string]map[string]string, toRomanian bool) map[string]map[string]string {
	result := make(map[string]map[string]string)
	for section, items := range features {
		ts := TranslateFeature(section, toRomanian)
		ti := make(map[string]string)
		for k, v := range items {
			ti[TranslateFeature(k, toRomanian)] = TranslateFeature(v, toRomanian)
		}
		result[ts] = ti
	}
	return result
}

// ─── Internal: Image Download ───────────────────────────────────────

func (s *Scraper) downloadImages(ctx context.Context, urls []string, listingID string) ([]string, error) {
	if len(urls) == 0 {
		return nil, nil
	}
	return DownloadImages(s.Client, urls, listingID, s.ListingsDir)
}

// ─── Internal: Geocoding ────────────────────────────────────────────

func (s *Scraper) geocodeListing(ctx context.Context, scraped *ScrapedData, listingID string) (float64, float64, string) {
	// Check cache first
	if scraped.MapLat != 0 || scraped.MapLng != 0 {
		return scraped.MapLat, scraped.MapLng, scraped.Title
	}

	if scraped.Address == "" || scraped.Address == "N/A" {
		return 0, 0, ""
	}

	// Check DB cache
	displayAddr := scraped.Address
	geocodingAddr := scraped.Address
	lat, lng, found := GetGeocodeCache(s.DB, displayAddr, geocodingAddr)
	if found {
		return lat, lng, displayAddr
	}

	// Perform geocoding
	lat, lng, _, mapTitle := GeocodeAddress(s.Client, displayAddr, geocodingAddr)

	// Save to cache
	if lat != 0 || lng != 0 {
		SaveGeocodeCache(s.DB, displayAddr, geocodingAddr, lat, lng, mapTitle)
	}

	return lat, lng, mapTitle
}

// ─── Internal: Data Assembly ────────────────────────────────────────

func (s *Scraper) buildListingData(
	id, urlStr string,
	scraped *ScrapedData,
	bilingual *BilingualData,
	localImages []string,
	lat, lng float64,
	mapTitle, templateName string,
) *database.ListingData {
	if templateName == "" {
		templateName = "luna"
	}

	// Build price JSON
	priceJSON := "{}"
	if scraped.PriceMap != nil && len(scraped.PriceMap) > 0 {
		b, err := json.Marshal(scraped.PriceMap)
		if err == nil {
			priceJSON = string(b)
		}
	}

	data := &database.ListingData{
		URL:          urlStr,
		Domain:       extractDomain(urlStr),
		PriceJSON:    priceJSON,
		Address:      scraped.Address,
		Contact:      scraped.Phone,
		TemplateName: templateName,
		Status:       "active",
		ListingType:  "for_sale",
		PropertyType: "apartment",
		Latitude:     lat,
		Longitude:    lng,
		MapTitle:     mapTitle,
	}

	// Set bilingual content
	if bilingual != nil {
		data.TitleRO = bilingual.RO.Title
		data.TitleRU = bilingual.RU.Title
		data.DescriptionRO = bilingual.RO.Description
		data.DescriptionRU = bilingual.RU.Description
		data.DisplayAddress = bilingual.RO.Address
		data.GeocodingAddress = bilingual.RO.Address

		// Features: convert bilingual maps to flat input slice
		data.Features = flattenFeatures("ro", bilingual.RO.Features)
		data.Features = append(data.Features, flattenFeatures("ru", bilingual.RU.Features)...)

		// Amenities
		data.Amenities = flattenAmenities("ro", bilingual.RO.Amenities)
		data.Amenities = append(data.Amenities, flattenAmenities("ru", bilingual.RU.Amenities)...)
	} else {
		data.TitleRO = scraped.Title
		data.TitleRU = scraped.Title
		data.DescriptionRO = scraped.Description
		data.DescriptionRU = scraped.Description
		data.DisplayAddress = scraped.Address
		data.GeocodingAddress = scraped.Address

		data.Features = flattenFeatures("ro", scraped.Features)
		data.Features = append(data.Features, flattenFeatures("ru", scraped.Features)...)
		data.Amenities = flattenAmenities("ro", scraped.Amenities)
	}

	// Images
	for i, imgURL := range scraped.Images {
		img := database.ListingImageInput{
			ImageURL: imgURL,
			Position: i,
		}
		if i < len(localImages) {
			img.LocalPath = localImages[i]
		}
		data.Images = append(data.Images, img)
	}

	return data
}

func flattenFeatures(lang string, features map[string]map[string]string) []database.ListingFeatureInput {
	var result []database.ListingFeatureInput
	for section, items := range features {
		for k, v := range items {
			result = append(result, database.ListingFeatureInput{
				Lang:         lang,
				Section:      section,
				FeatureKey:   k,
				FeatureValue: v,
			})
		}
	}
	return result
}

func flattenAmenities(lang string, amenities map[string]bool) []database.ListingAmenityInput {
	var result []database.ListingAmenityInput
	for k := range amenities {
		result = append(result, database.ListingAmenityInput{
			Lang:         lang,
			AmenityKey:   k,
			AmenityValue: "true",
		})
	}
	return result
}

// ─── Helpers ─────────────────────────────────────────────────────────

var userAgents = []string{
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

func extractListingID(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}
	// Find numeric segment in path (last numeric part)
	parts := strings.Split(strings.Trim(parsed.Path, "/"), "/")
	for i := len(parts) - 1; i >= 0; i-- {
		if matched, _ := regexp.MatchString(`^\d+$`, parts[i]); matched {
			return parts[i]
		}
	}
	return ""
}

func extractDomain(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}
	return parsed.Hostname()
}

func is999md(rawURL string) bool {
	return strings.Contains(rawURL, "999.md")
}

func detectLanguage(rawURL string) string {
	if strings.Contains(rawURL, "/ro/") || strings.Contains(rawURL, ".ro/") {
		return "ro"
	}
	if strings.Contains(rawURL, "/ru/") || strings.Contains(rawURL, ".ru/") {
		return "ru"
	}
	return "ro" // default
}

// truncStr truncates a string to max n runes for logging.
func truncStr(s string, n int) string {
	if len(s) <= n {
		return s
	}
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[:n]) + "..."
}


