package builder

import (
	"bytes"
	"database/sql"
	"fmt"
	"html/template"
	"log"
	"os"
	"path/filepath"
	"strings"

	"realagent/internal/database"
)

// ─── Types ──────────────────────────────────────────────────────────

// Builder orchestrates listing HTML generation.
type Builder struct {
	ListingsDir  string
	TemplatesDir string
	BaseURL      string
}

// BuildOptions configures a single HTML build.
type BuildOptions struct {
	ListingID    string
	TemplateName string
	SaveToFile   bool
	OutputPath   string
	BaseURL      string
}

// BuildResult holds the output of a build.
type BuildResult struct {
	HTML  string
	Path  string
	Error error
}

// TemplateData holds all data passed to listing templates.
type TemplateData struct {
	Listing     *database.ListingFull
	BaseURL     string
	Price       string
	Title       string
	HasMap      bool
	HasImages   bool
	HasFeatures bool
	Latitude    float64
	Longitude   float64
}

// New creates a new Builder.
func New(listingsDir, templatesDir, baseURL string) *Builder {
	if listingsDir == "" {
		listingsDir = "Listings"
	}
	if baseURL == "" {
		baseURL = "http://localhost:5000"
	}
	return &Builder{
		ListingsDir:  listingsDir,
		TemplatesDir: templatesDir,
		BaseURL:      baseURL,
	}
}

// BuildListingHTML generates HTML for a listing from database data.
func (b *Builder) BuildListingHTML(db *sql.DB, opts BuildOptions) (*BuildResult, error) {
	listing, err := database.GetListing(db, opts.ListingID)
	if err != nil {
		return &BuildResult{Error: fmt.Errorf("get listing: %w", err)}, nil
	}
	if listing == nil {
		return &BuildResult{Error: fmt.Errorf("listing %s not found", opts.ListingID)}, nil
	}

	baseURL := opts.BaseURL
	if baseURL == "" {
		baseURL = b.BaseURL
	}

	// Build template data
	price := listing.Price
	if price == "" {
		price = parsePriceSimple(listing.PriceJSON)
	}

	title := listing.TitleRO
	if title == "" {
		title = listing.TitleRU
	}
	if title == "" {
		title = "Property Listing"
	}

	data := TemplateData{
		Listing:     listing,
		BaseURL:     baseURL,
		Price:       price,
		Title:       title,
		HasMap:      listing.Map != nil,
		HasImages:   len(listing.Images) > 0,
		HasFeatures: len(listing.Features) > 0,
		Latitude:    listing.Latitude,
		Longitude:   listing.Longitude,
	}

	// Try to load template
	tmplName := opts.TemplateName
	if tmplName == "" {
		tmplName = listing.TemplateName
	}
	if tmplName == "" {
		tmplName = "luna"
	}

	var tmpl *template.Template
	tmplStr := getDefaultTemplate(tmplName)
	if b.TemplatesDir != "" {
		tplPath := filepath.Join(b.TemplatesDir, tmplName, "template.html")
		if _, err := os.Stat(tplPath); err == nil {
			tmpl, err = template.ParseFiles(tplPath)
			if err == nil {
				goto render
			}
			log.Printf("  Template parse error: %v, using default", err)
		}
	}

	tmpl, err = template.New("listing").Parse(tmplStr)
	if err != nil {
		return &BuildResult{Error: fmt.Errorf("template parse: %w", err)}, nil
	}

render:
	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, data); err != nil {
		return &BuildResult{Error: fmt.Errorf("template execute: %w", err)}, nil
	}

	html := buf.String()

	// Save to file if requested
	path := opts.OutputPath
	if opts.SaveToFile && path != "" {
		dir := filepath.Dir(path)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return &BuildResult{HTML: html, Error: fmt.Errorf("mkdir: %w", err)}, nil
		}
		if err := os.WriteFile(path, []byte(html), 0644); err != nil {
			return &BuildResult{HTML: html, Error: fmt.Errorf("write: %w", err)}, nil
		}
	} else if opts.SaveToFile {
		// Default path: Listings/{id}/index.html
		path = filepath.Join(b.ListingsDir, opts.ListingID, "index.html")
		dir := filepath.Dir(path)
		os.MkdirAll(dir, 0755)
		os.WriteFile(path, []byte(html), 0644)
	}

	return &BuildResult{HTML: html, Path: path}, nil
}

// ─── Default Templates ──────────────────────────────────────────────

func getDefaultTemplate(name string) string {
	switch strings.ToLower(name) {
	case "thunder":
		return thunderDefaultTemplate
	default:
		return lunaDefaultTemplate
	}
}

const lunaDefaultTemplate = `<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{.Title}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.header { background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
.header h1 { font-size: 28px; margin-bottom: 10px; }
.price { font-size: 32px; font-weight: 700; color: #2c7be5; }
.section { background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
.section h2 { font-size: 20px; margin-bottom: 15px; color: #2c3e50; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; }
.features { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px,1fr)); gap: 10px; }
.feature { padding: 8px 12px; background: #f8f9fa; border-radius: 6px; }
.feature-key { font-weight: 600; color: #555; }
.images { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px,1fr)); gap: 15px; }
.images img { width: 100%; height: 250px; object-fit: cover; border-radius: 8px; }
.desc { white-space: pre-line; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap: 15px; }
.info-item { padding: 15px; background: #f8f9fa; border-radius: 8px; }
.info-label { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; }
.info-value { font-size: 16px; font-weight: 600; margin-top: 4px; }
@media (max-width: 768px) { .header h1 { font-size: 22px; } .price { font-size: 26px; } }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{{.Title}}</h1>
    <div class="price">{{.Price}}</div>
  </div>

  {{if .HasImages}}
  <div class="section">
    <h2>Galerie</h2>
    <div class="images">
      {{range .Listing.Images}}
      <img src="{{if .LocalPath}}{{.LocalPath}}{{else}}{{.ImageURL}}{{end}}" alt="" loading="lazy">
      {{end}}
    </div>
  </div>
  {{end}}

  {{if .Listing.DescriptionRO}}<div class="section"><h2>Descriere</h2><div class="desc">{{.Listing.DescriptionRO}}</div></div>{{end}}
  {{if .Listing.DescriptionRU}}<div class="section"><h2>Описание</h2><div class="desc">{{.Listing.DescriptionRU}}</div></div>{{end}}

  <div class="section">
    <h2>Informații</h2>
    <div class="info-grid">
      {{if .Listing.Address}}<div class="info-item"><div class="info-label">Adresă</div><div class="info-value">{{.Listing.Address}}</div></div>{{end}}
      {{if .Listing.Contact}}<div class="info-item"><div class="info-label">Contact</div><div class="info-value">{{.Listing.Contact}}</div></div>{{end}}
      {{if .Listing.ListingType}}<div class="info-item"><div class="info-label">Tip</div><div class="info-value">{{.Listing.ListingType}}</div></div>{{end}}
      {{if .Listing.PropertyType}}<div class="info-item"><div class="info-label">Proprietate</div><div class="info-value">{{.Listing.PropertyType}}</div></div>{{end}}
    </div>
  </div>

  {{if .HasFeatures}}
  <div class="section">
    <h2>Caracteristici</h2>
    <div class="features">
      {{range .Listing.Features}}
      <div class="feature"><span class="feature-key">{{.FeatureKey}}:</span> {{.FeatureValue}}</div>
      {{end}}
    </div>
  </div>
  {{end}}

  {{if .HasMap}}
  <div class="section">
    <h2>Hartă</h2>
    <div id="map" style="height:400px;background:#e9ecef;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#6c757d;">
      Lat: {{.Latitude}}, Lng: {{.Longitude}}
    </div>
  </div>
  {{end}}
</div>
</body>
</html>`

const thunderDefaultTemplate = `<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{.Title}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Georgia', 'Times New Roman', serif; background: #1a1a2e; color: #eaeaea; }
.hero { background: linear-gradient(135deg, #16213e 0%, #0f3460 100%); padding: 60px 40px; text-align: center; }
.hero h1 { font-size: 36px; font-weight: 400; margin-bottom: 15px; letter-spacing: 1px; }
.price { font-size: 48px; font-weight: 700; color: #e94560; }
.content { max-width: 1000px; margin: 0 auto; padding: 40px 20px; }
.section { margin-bottom: 40px; }
.section h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 3px; color: #e94560; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }
.features { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px,1fr)); gap: 15px; }
.feature { padding: 15px; border: 1px solid #333; border-radius: 4px; }
.feature-key { color: #888; }
.images img { width: 100%; height: 400px; object-fit: cover; margin-bottom: 10px; }
.desc { font-size: 16px; line-height: 1.8; }
.info-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 20px; }
.info-item { padding: 20px; border: 1px solid #333; }
.info-label { font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #888; }
.info-value { font-size: 18px; margin-top: 8px; }
@media (max-width: 768px) { .hero h1 { font-size: 24px; } .price { font-size: 32px; } }
</style>
</head>
<body>
<div class="hero">
  <h1>{{.Title}}</h1>
  <div class="price">{{.Price}}</div>
</div>
<div class="content">
  {{if .HasImages}}
  <div class="section">
    <h2>Gallery</h2>
    {{range .Listing.Images}}
    <img src="{{if .LocalPath}}{{.LocalPath}}{{else}}{{.ImageURL}}{{end}}" alt="" loading="lazy">
    {{end}}
  </div>
  {{end}}

  {{if .Listing.DescriptionRO}}<div class="section"><h2>Description</h2><div class="desc">{{.Listing.DescriptionRO}}</div></div>{{end}}

  <div class="section">
    <h2>Details</h2>
    <div class="info-grid">
      {{if .Listing.Address}}<div class="info-item"><div class="info-label">Address</div><div class="info-value">{{.Listing.Address}}</div></div>{{end}}
      {{if .Listing.Contact}}<div class="info-item"><div class="info-label">Contact</div><div class="info-value">{{.Listing.Contact}}</div></div>{{end}}
    </div>
  </div>

  {{if .HasFeatures}}
  <div class="section">
    <h2>Features</h2>
    <div class="features">
      {{range .Listing.Features}}
      <div class="feature"><span class="feature-key">{{.FeatureKey}}:</span> {{.FeatureValue}}</div>
      {{end}}
    </div>
  </div>
  {{end}}
</div>
</body>
</html>`

// ─── Helpers ─────────────────────────────────────────────────────────

func parsePriceSimple(priceJSON string) string {
	if priceJSON == "" || priceJSON == "{}" {
		return ""
	}
	// Just return the raw JSON for now
	return priceJSON
}
