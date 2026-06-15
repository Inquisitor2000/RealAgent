package scraper

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// DownloadImages downloads list of image URLs concurrently and saves them to local disk.
// Returns list of local relative paths (e.g., "images/image_0.jpg") and any errors.
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

			ext := ".jpg"
			uLower := strings.ToLower(u)
			if strings.Contains(uLower, ".png") {
				ext = ".png"
			} else if strings.Contains(uLower, ".webp") {
				ext = ".webp"
			} else if strings.Contains(uLower, ".gif") {
				ext = ".gif"
			}

			fname := fmt.Sprintf("image_%d%s", i, ext)
			fullPath := filepath.Join(imgDir, fname)

			req, err := http.NewRequest("GET", u, nil)
			if err != nil {
				return
			}
			req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

			resp, err := client.Do(req)
			if err != nil {
				return
			}
			defer resp.Body.Close()

			if resp.StatusCode != 200 {
				return
			}

			out, err := os.Create(fullPath)
			if err != nil {
				return
			}
			defer out.Close()

			_, err = io.Copy(out, resp.Body)
			if err == nil {
				// Rel path matches standard DB convention: images/image_0.jpg
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
