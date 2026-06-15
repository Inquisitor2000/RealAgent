package scraper

import (
	"regexp"
	"strings"
	"unicode"
)

// ExtractPhone parses a Moldovan phone number from raw HTML page source.
func ExtractPhone(html string) string {
	// Primary: escaped Flight data format \"phone_numbers\":[\"373xxxxxxx\"]
	re := regexp.MustCompile(`\\"phone_numbers\\":\s*\[\s*\\"(\d+)`)
	matches := re.FindStringSubmatch(html)
	if len(matches) > 1 {
		phone := matches[1]
		return formatMoldovanPhone(phone)
	}

	// Backup: unescaped "phone_numbers":["373xxxxxxx"]
	re = regexp.MustCompile(`"phone_numbers"\s*:\s*\[\s*"([^"]+)"`)
	matches = re.FindStringSubmatch(html)
	if len(matches) > 1 {
		phone := matches[1]
		return formatMoldovanPhone(phone)
	}

	// Fallback: "phone":"373xxxxxxx"
	reFallback := regexp.MustCompile(`"phone"\s*:\s*"([^"]+)"`)
	matches = reFallback.FindStringSubmatch(html)
	if len(matches) > 1 {
		return formatMoldovanPhone(matches[1])
	}

	// Fallback: "phone_number":"373xxxxxxx"
	reJSONLike := regexp.MustCompile(`"phone_number"\s*:\s*"([^"]+)"`)
	matches = reJSONLike.FindStringSubmatch(html)
	if len(matches) > 1 {
		return formatMoldovanPhone(matches[1])
	}

	// Fallback: tel: links like <a href="tel:+373XXXXXXXX">
	reTel := regexp.MustCompile(`<a\s+href="tel:\+?(\d+)"`)
	matches = reTel.FindStringSubmatch(html)
	if len(matches) > 1 {
		return formatMoldovanPhone(matches[1])
	}

	return "N/A"
}

func formatMoldovanPhone(phone string) string {
	// Clean formatting
	phone = strings.ReplaceAll(phone, " ", "")
	phone = strings.ReplaceAll(phone, "-", "")
	phone = strings.ReplaceAll(phone, "(", "")
	phone = strings.ReplaceAll(phone, ")", "")
	phone = strings.ReplaceAll(phone, "+", "")

	// Reject if fewer than 6 digits (translation strings, garbage input)
	digitCount := 0
	for _, r := range phone {
		if unicode.IsDigit(r) {
			digitCount++
		}
	}
	if digitCount < 6 {
		return "N/A"
	}

	// Moldovan phones starting with country code 373
	if strings.HasPrefix(phone, "373") {
		number := phone[3:]
		if len(number) == 8 {
			return "+373 " + number[:2] + " " + number[2:5] + " " + number[5:]
		}
	}
	// Starting with 0
	if strings.HasPrefix(phone, "0") && len(phone) == 9 {
		number := phone[1:]
		return "+373 " + number[:2] + " " + number[2:5] + " " + number[5:]
	}
	// Just 8 digits
	if len(phone) == 8 {
		return "+373 " + phone[:2] + " " + phone[2:5] + " " + phone[5:]
	}

	// Return formatted if length matches, otherwise prefix with + if it looks like a number
	if len(phone) > 0 {
		return "+" + phone
	}
	return "N/A"
}
