package scraper

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"
)

type GeocodeResult struct {
	Lat         float64 `json:"lat,string"`
	Lon         float64 `json:"lon,string"`
	DisplayName string  `json:"display_name"`
	Class       string  `json:"class"`
	Type        string  `json:"type"`
	Address     struct {
		HouseNumber string `json:"house_number"`
		Road        string `json:"road"`
		Suburb      string `json:"suburb"`
		City        string `json:"city"`
		Country     string `json:"country"`
	} `json:"address"`
	Score   int
	Service string
}

type ParsedAddress struct {
	Street                 string
	StreetName             string
	District               string
	Building               string
	FullStreetWithBuilding string
	OriginalAddress        string
	CityMode               string
}

// Global rate limiter for Nominatim (1 request per second)
var nominatimLimiter = time.Tick(1 * time.Second)

// ParseAddressString parses a Moldovan address string into components.
func ParseAddressString(addr string) ParsedAddress {
	parts := strings.Split(addr, ",")
	for i := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}

	street := ""
	streetName := ""
	district := ""
	building := ""
	fullStreetWithBuilding := ""

	streetPrefixes := []string{
		"str.", "bd.", "bdul.", "strada", "bulevardul", "bulevardul.",
		"ул.", "бул.", "улица", "бульвар", "проспект", "пр.",
		"st.", "st ", "street", "avenue", "ave", "ave.", "blvd", "blvd.", "road", "rd", "rd.",
	}

	for i, part := range parts {
		hasStreetPrefix := false
		partLower := strings.ToLower(part)
		for _, prefix := range streetPrefixes {
			if strings.HasPrefix(partLower, prefix) || strings.Contains(partLower, " "+prefix) {
				hasStreetPrefix = true
				break
			}
		}

		streetPatternSuffixAfter := regexp.MustCompile(`(?i)^([A-Za-zĂÂÎȘȚăâîșțА-Яа-я\s]+)\s+(?:St\.?|Street|Str\.?|strada|ул\.?|Ave\.?|Avenue|Blvd\.?|Boulevard|Rd\.?|Road)\s+([\d]+[\w/-]*)$`)
		streetPatternSuffixBefore := regexp.MustCompile(`(?i)^([A-Za-zĂÂÎȘȚăâîșțА-Яа-я\s]+(?:St\.?|Street|Str\.?|strada|ул\.?|Ave\.?|Avenue|Blvd\.?|Boulevard|Rd\.?|Road)?)\s+([\d]+[\w/-]*)$`)

		suffixAfterMatch := streetPatternSuffixAfter.FindStringSubmatch(part)
		suffixBeforeMatch := streetPatternSuffixBefore.FindStringSubmatch(part)

		if hasStreetPrefix || len(suffixAfterMatch) > 0 || len(suffixBeforeMatch) > 0 {
			street = part
			fullStreetWithBuilding = part

			if len(suffixAfterMatch) > 0 {
				streetName = strings.TrimSpace(suffixAfterMatch[1])
				building = strings.TrimSpace(suffixAfterMatch[2])
				reSuffix := regexp.MustCompile(`(?i)\s+(?:St\.?|Street|Str\.?|strada|ул\.?|Ave\.?|Avenue|Blvd\.?|Boulevard|Rd\.?|Road)\s*$`)
				streetName = reSuffix.ReplaceAllString(streetName, "")
			} else if len(suffixBeforeMatch) > 0 {
				streetName = strings.TrimSpace(suffixBeforeMatch[1])
				building = strings.TrimSpace(suffixBeforeMatch[2])
			} else {
				rePrefix := regexp.MustCompile(`(?i)^(?:str\.|bd\.|bdul\.|strada|bulevardul\.?|ул\.|бул\.|улица|бульвар|проспект|пр\.)\s+(.+)`)
				prefixMatch := rePrefix.FindStringSubmatch(part)
				if len(prefixMatch) > 1 {
					streetWithNumber := strings.TrimSpace(prefixMatch[1])
					numberMatch := regexp.MustCompile(`(?i)(.+?)\s+([\d]+[\w/-]*)$`).FindStringSubmatch(streetWithNumber)
					if len(numberMatch) > 2 {
						streetName = strings.TrimSpace(numberMatch[1])
						building = strings.TrimSpace(numberMatch[2])
					} else {
						streetName = streetWithNumber
					}
				}
			}

			if building == "" && i+1 < len(parts) {
				nextPart := parts[i+1]
				if regexp.MustCompile(`^[\d]+[\w/-]*$`).MatchString(nextPart) {
					building = nextPart
					fullStreetWithBuilding += ", " + building
				}
			}
		} else if !strings.Contains(partLower, "mun.") && partLower != "chișinău" && partLower != "chisinau" && partLower != "moldova" && partLower != "кишинэу" && partLower != "кишинев" && partLower != "молдова" {
			if regexp.MustCompile(`(?i)^MD-?\d{4}$`).MatchString(part) {
				continue
			}
			if building == "" && regexp.MustCompile(`^[\d]+[\w/-]*$`).MatchString(part) {
				building = part
				if street != "" {
					fullStreetWithBuilding += ", " + building
				}
			} else if district == "" {
				district = part
			}
		}
	}

	cleanStreetName := streetName
	for _, prefix := range streetPrefixes {
		re := regexp.MustCompile(`(?i)\b` + regexp.QuoteMeta(prefix) + `\b`)
		cleanStreetName = re.ReplaceAllString(cleanStreetName, "")
	}
	cleanStreetName = regexp.MustCompile(`\s+`).ReplaceAllString(cleanStreetName, " ")
	cleanStreetName = strings.TrimSpace(cleanStreetName)

	return ParsedAddress{
		Street:                 street,
		StreetName:             cleanStreetName,
		District:               district,
		Building:               building,
		FullStreetWithBuilding: fullStreetWithBuilding,
		OriginalAddress:        addr,
	}
}

// GetGeocodeCache checks the SQLite db for cached geocoding coordinates.
func GetGeocodeCache(db *sql.DB, displayAddr, geocodingAddr string) (float64, float64, bool) {
	keyStr := fmt.Sprintf("%s|%s", strings.ToLower(strings.TrimSpace(displayAddr)), strings.ToLower(strings.TrimSpace(geocodingAddr)))
	hasher := sha256.New()
	hasher.Write([]byte(keyStr))
	key := hex.EncodeToString(hasher.Sum(nil))

	var lat, lng float64
	err := db.QueryRow("SELECT lat, lng FROM geocode_cache WHERE key = ?", key).Scan(&lat, &lng)
	if err == nil {
		return lat, lng, true
	}
	return 0, 0, false
}

// SaveGeocodeCache saves successfully geocoded coordinates to the db.
func SaveGeocodeCache(db *sql.DB, displayAddr, geocodingAddr string, lat, lng float64, title string) {
	keyStr := fmt.Sprintf("%s|%s", strings.ToLower(strings.TrimSpace(displayAddr)), strings.ToLower(strings.TrimSpace(geocodingAddr)))
	hasher := sha256.New()
	hasher.Write([]byte(keyStr))
	key := hex.EncodeToString(hasher.Sum(nil))

	db.Exec("INSERT OR REPLACE INTO geocode_cache (key, lat, lng, title) VALUES (?, ?, ?, ?)", key, lat, lng, title)
}

// ScoreResult assigns confidence score to a geocoding result.
func ScoreResult(res GeocodeResult, parsed ParsedAddress) int {
	score := 0
	name := strings.ToLower(res.DisplayName)
	originalAddr := strings.ToLower(parsed.OriginalAddress)

	cityNames := []string{"chișinău", "chisinau", "bălți", "balti", "tiraspol", "bender", "tighina", "cahul", "ungheni", "soroca", "orhei", "comrat", "cricova", "durlești", "codru", "кишинэу", "кишинев"}
	cityFromAddress := ""
	for _, city := range cityNames {
		if strings.Contains(originalAddr, city) {
			cityFromAddress = city
			break
		}
	}
	if parsed.CityMode == "default" {
		cityFromAddress = "chișinău"
	}

	// 1. City scoring (25 max)
	if cityFromAddress != "" {
		if strings.Contains(name, cityFromAddress) {
			score += 25
		} else {
			for _, otherCity := range cityNames {
				if otherCity != cityFromAddress && strings.Contains(name, otherCity) {
					return -100 // Heavy penalty for wrong city
				}
			}
		}
	}

	// 2. Street scoring (40 max)
	if parsed.StreetName != "" && strings.Contains(name, strings.ToLower(parsed.StreetName)) {
		score += 40
	}

	// 2.5. District scoring (20 bonus, -50 wrong district)
	if parsed.District != "" {
		distLower := strings.ToLower(parsed.District)
		if strings.Contains(name, distLower) {
			score += 20
		} else {
			knownDistricts := []string{"botanica", "centru", "ciocana", "râșcani", "rîșcani", "buiucani", "telecentru", "durlești", "codru", "sîngera", "singera"}
			for _, otherDistrict := range knownDistricts {
				if otherDistrict != distLower && strings.Contains(name, otherDistrict) {
					score -= 50
					break
				}
			}
		}
	}

	// 3. House number scoring (35 max)
	if parsed.Building != "" && strings.Contains(name, strings.ToLower(parsed.Building)) {
		score += 35
	}

	// Building bonus
	resType := strings.ToLower(res.Type)
	resClass := strings.ToLower(res.Class)
	hasHouseNumber := res.Address.HouseNumber != ""

	if parsed.Building != "" {
		hasBuildingInName := strings.Contains(name, strings.ToLower(parsed.Building))
		isBuildingType := (resType == "house" || resType == "apartments" || resType == "building" || resType == "residential") ||
			(resClass == "building" || resClass == "place")
		if isBuildingType && (hasHouseNumber || hasBuildingInName) {
			score += 40
		} else if resType == "road" || resType == "residential" || resType == "street" || resClass == "highway" {
			score -= 15
		}
	}

	if score > 100 {
		return 100
	}
	if score < 0 {
		return 0
	}
	return score
}

// prioritizeCoordinates extracts the best coordinates from a list of GeocodeResults.
func prioritizeCoordinates(results []GeocodeResult, parsed ParsedAddress) *GeocodeResult {
	var buildingResults []GeocodeResult
	var cityResults []GeocodeResult
	var districtResults []GeocodeResult
	var streetResults []GeocodeResult

	detectedCity := ""
	originalAddr := strings.ToLower(parsed.OriginalAddress)
	cityNames := []string{"chișinău", "chisinau", "bălți", "balti", "tiraspol", "bender", "tighina", "cahul", "ungheni", "soroca", "orhei", "comrat", "кишинэу", "кишинев"}
	for _, cname := range cityNames {
		if strings.Contains(originalAddr, cname) {
			detectedCity = cname
			break
		}
	}
	if parsed.CityMode == "default" {
		detectedCity = "chișinău"
	}

	for _, res := range results {
		name := strings.ToLower(res.DisplayName)
		resType := strings.ToLower(res.Type)
		resClass := strings.ToLower(res.Class)
		hasHouseNumber := res.Address.HouseNumber != ""
		hasBuildingInName := parsed.Building != "" && strings.Contains(name, strings.ToLower(parsed.Building))

		isBuilding := (resType == "house" || resType == "apartments" || resType == "building" || resType == "residential" || resClass == "building" || resClass == "place") &&
			(hasHouseNumber || hasBuildingInName) && parsed.Building != ""

		if isBuilding {
			buildingResults = append(buildingResults, res)
		} else if resType == "city" || resType == "town" || resType == "municipality" || (resClass == "place" || resClass == "boundary") && (detectedCity != "" && strings.Contains(name, detectedCity)) {
			cityResults = append(cityResults, res)
		} else if parsed.District != "" && strings.Contains(name, strings.ToLower(parsed.District)) && (resType == "suburb" || resType == "neighbourhood" || resType == "quarter" || resType == "district") {
			districtResults = append(districtResults, res)
		} else if parsed.StreetName != "" && strings.Contains(name, strings.ToLower(parsed.StreetName)) {
			streetResults = append(streetResults, res)
		}
	}

	if len(buildingResults) > 0 {
		sort.Slice(buildingResults, func(i, j int) bool {
			return ScoreResult(buildingResults[i], parsed) > ScoreResult(buildingResults[j], parsed)
		})
		return &buildingResults[0]
	}
	if len(cityResults) > 0 {
		sort.Slice(cityResults, func(i, j int) bool {
			return ScoreResult(cityResults[i], parsed) > ScoreResult(cityResults[j], parsed)
		})
		return &cityResults[0]
	}
	if len(districtResults) > 0 {
		sort.Slice(districtResults, func(i, j int) bool {
			return ScoreResult(districtResults[i], parsed) > ScoreResult(districtResults[j], parsed)
		})
		return &districtResults[0]
	}
	if len(streetResults) > 0 {
		sort.Slice(streetResults, func(i, j int) bool {
			return ScoreResult(streetResults[i], parsed) > ScoreResult(streetResults[j], parsed)
		})
		return &streetResults[0]
	}
	return nil
}

// QueryNominatim sends a request to OSM Nominatim API with rate limits.
func QueryNominatim(client *http.Client, query string) ([]GeocodeResult, error) {
	<-nominatimLimiter // Rate limit 1 request/sec

	apiURL := fmt.Sprintf("https://nominatim.openstreetmap.org/search?q=%s&format=json&limit=5&countrycodes=md&addressdetails=1", url.QueryEscape(query))
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "RealAgent/1.0 (Go Scraper Geocoder)")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("nominatim returned status %d", resp.StatusCode)
	}

	var results []GeocodeResult
	if err := json.NewDecoder(resp.Body).Decode(&results); err != nil {
		return nil, err
	}

	for i := range results {
		results[i].Service = "nominatim"
	}
	return results, nil
}

// QueryPhoton sends a request to Photon API with bbox constraints.
func QueryPhoton(client *http.Client, query string) ([]GeocodeResult, error) {
	// bbox=28.6,46.8,29.2,47.2 restricts to Chișinău area
	apiURL := fmt.Sprintf("https://photon.komoot.io/api/?q=%s&limit=5&bbox=28.6,46.8,29.2,47.2", url.QueryEscape(query))
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "RealAgent/1.0 (Go Scraper Geocoder)")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("photon returned status %d", resp.StatusCode)
	}

	var data struct {
		Features []struct {
			Geometry struct {
				Coordinates []float64 `json:"coordinates"` // [lon, lat]
			} `json:"geometry"`
			Properties map[string]interface{} `json:"properties"`
		} `json:"features"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}

	var results []GeocodeResult
	for _, f := range data.Features {
		if len(f.Geometry.Coordinates) < 2 {
			continue
		}
		name, _ := f.Properties["name"].(string)
		street, _ := f.Properties["street"].(string)
		if street != "" {
			name = name + ", " + street
		}
		osmValue, _ := f.Properties["osm_value"].(string)
		osmKey, _ := f.Properties["osm_key"].(string)

		var res GeocodeResult
		res.Lat = f.Geometry.Coordinates[1]
		res.Lon = f.Geometry.Coordinates[0]
		res.DisplayName = name
		res.Type = osmValue
		res.Class = osmKey
		res.Service = "photon"
		results = append(results, res)
	}

	return results, nil
}

// GeocodeAddress performs geocoding using Nominatim and Photon with fallback.
func GeocodeAddress(client *http.Client, displayAddr, geocodingAddr string) (float64, float64, int, string) {
	if geocodingAddr == "" || geocodingAddr == "N/A" {
		return 0, 0, 0, ""
	}

	parsed := ParseAddressString(geocodingAddr)

	// Try translation of street names if Cyrillic
	if DetectCyrillic(geocodingAddr) {
		parsed.StreetName = TranslateRussianToRomanian(parsed.StreetName)
		parsed.District = TranslateRussianToRomanian(parsed.District)
	}

	// 1. Try Nominatim on geocoding address
	results, err := QueryNominatim(client, geocodingAddr)
	if err == nil && len(results) > 0 {
		if best := prioritizeCoordinates(results, parsed); best != nil {
			score := ScoreResult(*best, parsed)
			if score >= 90 {
				return best.Lat, best.Lon, score, best.DisplayName
			}
		}
	}

	// 2. Try Photon on geocoding address
	photonResults, err := QueryPhoton(client, geocodingAddr)
	if err == nil && len(photonResults) > 0 {
		if best := prioritizeCoordinates(photonResults, parsed); best != nil {
			score := ScoreResult(*best, parsed)
			if score >= 90 {
				return best.Lat, best.Lon, score, best.DisplayName
			}
		}
	}

	// Merge all results and get best overall
	var allResults []GeocodeResult
	allResults = append(allResults, results...)
	allResults = append(allResults, photonResults...)

	if len(allResults) > 0 {
		if best := prioritizeCoordinates(allResults, parsed); best != nil {
			score := ScoreResult(*best, parsed)
			return best.Lat, best.Lon, score, best.DisplayName
		}
	}

	// Default fallback to Chișinău Center
	return 47.0105, 28.8638, 25, "Chișinău, Moldova"
}
