package scraper

import (
	"bytes"
	"regexp"
	"strconv"
	"strings"

	"golang.org/x/net/html"
)

type ScrapedData struct {
	Title       string
	Description string
	PriceMap    map[string]string
	Features    map[string]map[string]string // e.g. ["Caracteristici"]["Количество комнат"] = "2"
	Amenities   map[string]bool
	Address     string
	Images      []string
	MapLat      float64
	MapLng      float64
	HasMapData  bool
	Phone       string // extracted from raw HTML, not from parsed DOM
	SourceLang  string // "ro" or "ru"
}

// CleanDescriptionHTML cleans description HTML, converts <br> to newlines, and preserves structure.
func CleanDescriptionHTML(htmlStr string) string {
	// 1. Remove script, style, iframe, object, embed tags
	reDangerous := regexp.MustCompile(`(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>`)
	htmlStr = reDangerous.ReplaceAllString(htmlStr, "")

	// 2. Convert <br> variants to newlines
	reBr := regexp.MustCompile(`(?i)<br\s*/?></br>|<br\s*/?>`)
	htmlStr = reBr.ReplaceAllString(htmlStr, "\n")

	// 3. Convert block elements to newlines
	reBlocks := regexp.MustCompile(`(?i)</p>|</div>|</h[1-6]>`)
	htmlStr = reBlocks.ReplaceAllString(htmlStr, "\n")

	// 4. Remove other tag wrappers but keep contents
	reTags := regexp.MustCompile(`(?i)<[^>]+>`)
	htmlStr = reTags.ReplaceAllString(htmlStr, "")

	// 5. Remove URLs
	reURL1 := regexp.MustCompile(`(?i)https?://[^\s<>"]+`)
	htmlStr = reURL1.ReplaceAllString(htmlStr, "")
	reURL2 := regexp.MustCompile(`(?i)www\.[^\s<>"]+`)
	htmlStr = reURL2.ReplaceAllString(htmlStr, "")

	// 6. Normalize whitespace
	reSpaces := regexp.MustCompile(`[ \t]+`)
	htmlStr = reSpaces.ReplaceAllString(htmlStr, " ")

	reLines := regexp.MustCompile(` *\n *`)
	htmlStr = reLines.ReplaceAllString(htmlStr, "\n")

	reMultiLines := regexp.MustCompile(`\n{3,}`)
	htmlStr = reMultiLines.ReplaceAllString(htmlStr, "\n\n")

	return strings.TrimSpace(htmlStr)
}

// ─── DOM Helpers ───────────────────────────────────────────────────

func findNode(n *html.Node, match func(*html.Node) bool) *html.Node {
	if match(n) {
		return n
	}
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		if found := findNode(c, match); found != nil {
			return found
		}
	}
	return nil
}

func findNodes(n *html.Node, match func(*html.Node) bool) []*html.Node {
	var nodes []*html.Node
	var recurse func(*html.Node)
	recurse = func(node *html.Node) {
		if match(node) {
			nodes = append(nodes, node)
		}
		for c := node.FirstChild; c != nil; c = c.NextSibling {
			recurse(c)
		}
	}
	recurse(n)
	return nodes
}

func hasClass(n *html.Node, className string) bool {
	if n.Type != html.ElementNode {
		return false
	}
	for _, attr := range n.Attr {
		if attr.Key == "class" {
			classes := strings.Fields(attr.Val)
			for _, c := range classes {
				if c == className {
					return true
				}
			}
		}
	}
	return false
}

func getAttr(n *html.Node, key string) string {
	for _, attr := range n.Attr {
		if attr.Key == key {
			return attr.Val
		}
	}
	return ""
}

func getText(n *html.Node) string {
	var sb strings.Builder
	var recurse func(*html.Node)
	recurse = func(node *html.Node) {
		if node.Type == html.TextNode {
			sb.WriteString(node.Data)
		}
		for c := node.FirstChild; c != nil; c = c.NextSibling {
			recurse(c)
		}
	}
	recurse(n)
	return sb.String()
}

func getInnerHTML(n *html.Node) string {
	var buf bytes.Buffer
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		html.Render(&buf, c)
	}
	return buf.String()
}

// ─── Parse Core Functions ──────────────────────────────────────────

func ParseHTML(htmlStr string) (*ScrapedData, error) {
	doc, err := html.Parse(strings.NewReader(htmlStr))
	if err != nil {
		return nil, err
	}

	data := &ScrapedData{}

	// 1. Title — try <h1> first, then og:title meta, then <title>
	h1Node := findNode(doc, func(n *html.Node) bool {
		return n.Type == html.ElementNode && n.Data == "h1"
	})
	if h1Node != nil {
		data.Title = strings.TrimSpace(getText(h1Node))
	}
	if data.Title == "" {
		// Fallback: <meta property="og:title">
		metaNode := findNode(doc, func(n *html.Node) bool {
			return n.Type == html.ElementNode && n.Data == "meta" &&
				getAttr(n, "property") == "og:title"
		})
		if metaNode != nil {
			data.Title = strings.TrimSpace(getAttr(metaNode, "content"))
		}
	}
	if data.Title == "" {
		// Last resort: <title> tag
		titleNode := findNode(doc, func(n *html.Node) bool {
			return n.Type == html.ElementNode && n.Data == "title"
		})
		if titleNode != nil {
			data.Title = strings.TrimSpace(getText(titleNode))
		}
	}

	// 2. Description — prefer styles_description__body__qh1qw (just the text),
	// then data-block="description" (stable container), then class fallback.
	descBody := findNode(doc, func(n *html.Node) bool {
		return hasClass(n, "styles_description__body__qh1qw")
	})
	if descBody != nil {
		data.Description = strings.TrimSpace(getText(descBody))
	} else {
		descNode := findNode(doc, func(n *html.Node) bool {
			return getAttr(n, "data-block") == "description"
		})
		if descNode == nil {
			descNode = findNode(doc, func(n *html.Node) bool {
				return hasClass(n, "styles_description__Z_xcm")
			})
		}
		if descNode != nil {
			rawHTML := getInnerHTML(descNode)
			rawHTML = strings.ReplaceAll(rawHTML, "\r\n", "\n")
			rawHTML = strings.TrimSpace(rawHTML)

			reBr := regexp.MustCompile(`(?i)<br\s*/?>`)
			rawHTML = reBr.ReplaceAllString(rawHTML, "<br>")

			if !strings.Contains(strings.ToLower(rawHTML), "<br") {
				token := "___NL2___"
				reNL := regexp.MustCompile(`\n{2,}`)
				rawHTML = reNL.ReplaceAllString(rawHTML, token)
				rawHTML = strings.ReplaceAll(rawHTML, "\n", "<br>")
				rawHTML = strings.ReplaceAll(rawHTML, token, "<br><br>")
			}
			data.Description = CleanDescriptionHTML(rawHTML)
		} else {
			data.Description = "N/A"
		}
	}

	// 3. Price
	priceContainer := findNode(doc, func(n *html.Node) bool {
		return hasClass(n, "styles_price__uQcAd")
	})
	if priceContainer != nil {
		data.PriceMap = parsePriceMap(priceContainer)
	} else {
		data.PriceMap = make(map[string]string)
	}

	// 4. Features & Amenities
	data.Features, data.Amenities = parseFeaturesAndAmenities(doc)

	// 5. Address
	data.Address = parseAddress(doc)

	// 6. Images
	data.Images = parseImages(doc)

	// 7. Yandex Map coordinates
	data.MapLat, data.MapLng, data.HasMapData = parseMapCoordinates(doc)

	return data, nil
}

func parsePriceMap(priceContainer *html.Node) map[string]string {
	priceMap := make(map[string]string)
	mainTag := findNode(priceContainer, func(n *html.Node) bool {
		return hasClass(n, "styles_price__main__kz3DX")
	})
	if mainTag != nil {
		text := strings.TrimSpace(getText(mainTag))
		text = strings.ReplaceAll(text, "\u00a0", " ") // Replace non-breaking spaces

		re := regexp.MustCompile(`([\d\s]+)\s*(\D+)$`)
		matches := re.FindStringSubmatch(text)
		if len(matches) > 2 {
			amt := strings.TrimSpace(matches[1])
			sym := strings.TrimSpace(matches[2])
			key := sym
			if sym == "€" {
				key = "EUR"
			} else if sym == "$" {
				key = "USD"
			}
			priceMap[key] = amt + " " + sym
		} else {
			priceMap["MAIN"] = text
		}
	}
	return priceMap
}

func parseFeaturesAndAmenities(doc *html.Node) (map[string]map[string]string, map[string]bool) {
	features := make(map[string]map[string]string)
	amenities := make(map[string]bool)

	groups := findNodes(doc, func(n *html.Node) bool {
		return hasClass(n, "styles_group__VzZgm")
	})

	for _, grp := range groups {
		// Section name: try data-testid (stable), then <label>, then <h2>
		sectionName := getAttr(grp, "data-testid")
		if sectionName == "" {
			labelNode := findNode(grp, func(n *html.Node) bool {
				return hasClass(n, "styles_group__label__oco2f")
			})
			if labelNode != nil {
				sectionName = strings.TrimSpace(getText(labelNode))
			}
		}
		if sectionName == "" {
			hdrNode := findNode(grp, func(n *html.Node) bool {
				return n.Type == html.ElementNode && n.Data == "h2"
			})
			if hdrNode != nil {
				sectionName = strings.TrimSpace(getText(hdrNode))
			}
		}
		if sectionName == "" {
			sectionName = "Features"
		}

		items := findNodes(grp, func(n *html.Node) bool {
			return hasClass(n, "styles_group__feature__GsOUi")
		})

		dataMap := make(map[string]string)
		var simple []string

		for _, li := range items {
			kElem := findNode(li, func(n *html.Node) bool {
				return hasClass(n, "styles_group__key__SXHV5")
			})
			vElem := findNode(li, func(n *html.Node) bool {
				return hasClass(n, "styles_group__value__BlYqu") || hasClass(n, "styles_group__link__GA7Xf")
			})

			if kElem != nil {
				k := strings.TrimSpace(getText(kElem))
				if vElem != nil {
					v := strings.TrimSpace(getText(vElem))
					if v != "" {
						dataMap[k] = v
					} else {
						// Empty value (e.g. Adăugător checkmarks) → treat as simple amenity
						simple = append(simple, k)
					}
				} else {
					simple = append(simple, k)
				}
			}
		}

		isCaracteristici := sectionName == "Характеристики" || sectionName == "Caracteristici"

		if isCaracteristici {
			if len(dataMap) > 0 {
				features[sectionName] = dataMap
			} else if len(simple) > 0 {
				m := make(map[string]string)
				for _, s := range simple {
					m[s] = "true"
				}
				features[sectionName] = m
			}
		} else {
			if len(dataMap) > 0 {
				for k, v := range dataMap {
					amenities[k+": "+v] = true
				}
			} else {
				for _, s := range simple {
					amenities[s] = true
				}
			}
		}
	}

	return features, amenities
}

func parseAddress(doc *html.Node) string {
	// Address is in the map title: styles_map__title__UgISm
	mapTitle := findNode(doc, func(n *html.Node) bool {
		return hasClass(n, "styles_map__title__UgISm")
	})
	if mapTitle != nil {
		return strings.TrimSpace(getText(mapTitle))
	}

	// Fallback: data-block="map" container
	mapBlock := findNode(doc, func(n *html.Node) bool {
		return getAttr(n, "data-block") == "map"
	})
	if mapBlock != nil {
		return strings.TrimSpace(getText(mapBlock))
	}

	// Last resort: region selector (just "Moldova", not useful)
	regionContainer := findNode(doc, func(n *html.Node) bool {
		return hasClass(n, "styles_regions__rUPBP")
	})
	if regionContainer != nil {
		return strings.TrimSpace(getText(regionContainer))
	}
	return "N/A"
}

func parseImages(doc *html.Node) []string {
	var images []string
	seen := make(map[string]bool)

	buttons := findNodes(doc, func(n *html.Node) bool {
		return n.Type == html.ElementNode && n.Data == "button" && getAttr(n, "data-src") != ""
	})

	for _, btn := range buttons {
		src := getAttr(btn, "data-src")
		if src != "" && !seen[src] {
			seen[src] = true
			images = append(images, src)
		}
	}
	return images
}

func parseMapCoordinates(doc *html.Node) (float64, float64, bool) {
	// Try 1: map link href contains map_lat=...&map_lon=... params
	mapLink := findNode(doc, func(n *html.Node) bool {
		return hasClass(n, "styles_map__link__seGAY")
	})
	if mapLink != nil {
		href := getAttr(mapLink, "href")
		if href != "" {
			re := regexp.MustCompile(`map_lat=([-\d.]+)&map_lon=([-\d.]+)`)
			matches := re.FindStringSubmatch(href)
			if len(matches) > 2 {
				lat, err1 := strconv.ParseFloat(matches[1], 64)
				lng, err2 := strconv.ParseFloat(matches[2], 64)
				if err1 == nil && err2 == nil {
					return lat, lng, true
				}
			}
		}
	}

	// Try 2: ymaps.ready script (may not be in SSR)
	scripts := findNodes(doc, func(n *html.Node) bool {
		return n.Type == html.ElementNode && n.Data == "script"
	})

	re := regexp.MustCompile(`center:\s*\[(\d+\.\d+),\s*(\d+\.\d+)\]`)
	for _, s := range scripts {
		content := getText(s)
		if strings.Contains(content, "ymaps.ready") {
			matches := re.FindStringSubmatch(content)
			if len(matches) > 2 {
				lat, _ := strconv.ParseFloat(matches[1], 64)
				lng, _ := strconv.ParseFloat(matches[2], 64)
				return lat, lng, true
			}
		}
	}
	return 0, 0, false
}
