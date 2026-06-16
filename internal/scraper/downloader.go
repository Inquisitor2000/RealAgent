package scraper

import (
	"bytes"
	"fmt"
	"image"
	"image/gif"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/deepteams/webp"
)

// DownloadImages downloads list of image URLs concurrently, converts them to WebP,
// and saves them to local disk. Animated GIFs are preserved as-is.
// Returns list of local relative paths (e.g., "images/image_0.webp") and any errors.
func DownloadImages(client *http.Client, urls []string, listingID, listingsDir string) ([]string, error) {
	// Create directory: Listings/<listingID>/images
	imgDir := filepath.Join(listingsDir, listingID, "images")
	if err := os.MkdirAll(imgDir, 0755); err != nil {
		return nil, fmt.Errorf("create images dir: %w", err)
	}

	localPaths := make([]string, len(urls))
	var wg sync.WaitGroup
	sem := make(chan struct{}, 4) // Max 4 concurrent downloads

	for idx, imgURL := range urls {
		wg.Add(1)
		sem <- struct{}{}
		go func(i int, u string) {
			defer wg.Done()
			defer func() { <-sem }()

			req, err := http.NewRequest("GET", u, nil)
			if err != nil {
				log.Printf("  [images] req error [%d] %s: %v", i, u, err)
				return
			}
			req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

			resp, err := client.Do(req)
			if err != nil {
				log.Printf("  [images] http error [%d] %s: %v", i, u, err)
				return
			}
			defer resp.Body.Close()

			if resp.StatusCode != 200 {
				log.Printf("  [images] bad status [%d] %s: %d", i, u, resp.StatusCode)
				return
			}

			data, err := io.ReadAll(resp.Body)
			if err != nil {
				log.Printf("  [images] read error [%d] %s: %v", i, u, err)
				return
			}

			// Keep animated GIFs as-is (WebP animation support is limited)
			if isAnimatedGIF(u, data) {
				fname := fmt.Sprintf("image_%d.gif", i)
				fullPath := filepath.Join(imgDir, fname)
				if err := os.WriteFile(fullPath, data, 0644); err == nil {
					localPaths[i] = "images/" + fname
				}
				return
			}

			// Try to decode and re-encode as WebP
			img, err := decodeAnyImage(data)
			if err != nil {
				// Fallback: save as-is with original format
				log.Printf("  [images] decode failed [%d] %s: %v — saving as-is (%s)", i, u, err, guessExt(u))
				fname := fmt.Sprintf("image_%d%s", i, guessExt(u))
				fullPath := filepath.Join(imgDir, fname)
				if err := os.WriteFile(fullPath, data, 0644); err == nil {
					localPaths[i] = "images/" + fname
				}
				return
			}

			// Encode as WebP
			var buf bytes.Buffer
			if err := webp.Encode(&buf, img, &webp.Options{Quality: 85}); err != nil {
				log.Printf("  [images] webp encode error [%d] %s: %v", i, u, err)
				return
			}

			fname := fmt.Sprintf("image_%d.webp", i)
			fullPath := filepath.Join(imgDir, fname)
			if err := os.WriteFile(fullPath, buf.Bytes(), 0644); err == nil {
				localPaths[i] = "images/" + fname
			}
		}(idx, imgURL)
	}

	wg.Wait()

	// Filter out any failed downloads
	var filtered []string
	for _, p := range localPaths {
		if p != "" {
			filtered = append(filtered, p)
		}
	}

	return filtered, nil
}

// isAnimatedGIF returns true if the URL or content suggests an animated GIF.
func isAnimatedGIF(url string, data []byte) bool {
	u := strings.ToLower(url)
	if !strings.Contains(u, ".gif") {
		return false
	}
	// Check for multiple frames in GIF header
	if len(data) > 10 && data[0] == 'G' && data[1] == 'I' && data[2] == 'F' {
		g, err := gif.DecodeAll(bytes.NewReader(data))
		if err == nil && len(g.Image) > 1 {
			return true
		}
	}
	return true // URL says .gif even if single-frame
}

// decodeAnyImage tries standard image decoders (JPEG, PNG, GIF) then WebP.
func decodeAnyImage(data []byte) (image.Image, error) {
	img, _, err := image.Decode(bytes.NewReader(data))
	if err == nil {
		return img, nil
	}
	// Try WebP decoder
	return webp.Decode(bytes.NewReader(data))
}

// guessExt returns a file extension based on URL hints.
func guessExt(u string) string {
	u = strings.ToLower(u)
	switch {
	case strings.Contains(u, ".png"):
		return ".png"
	case strings.Contains(u, ".webp"):
		return ".webp"
	case strings.Contains(u, ".gif"):
		return ".gif"
	default:
		return ".jpg"
	}
}
