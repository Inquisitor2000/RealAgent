package scraper

import (
	"regexp"
	"strings"
)

// PropertyFeatureTranslations maps Russian property features/characteristics to Romanian.
var PropertyFeatureTranslations = map[string]string{
	// Building Features
	"Готова к въезду":       "Gata de mutat",
	"Готова для проживания": "Gata pentru mutare",
	"Пристройка":            "Anexă",
	"Терраса":               "Terasă",
	"Отдельный вход":        "Intrare separată",
	"Парковая зона":         "Zonă cu parc",
	"Зеленая зона":          "Zonă verde",

	// Interior Features
	"Меблирована":        "Mobilată",
	"С мебелью":          "Cu mobilă",
	"Мебель включена":    "Mobilier inclus",
	"С бытовой техникой": "Cu tehnică electrocasnică",
	"С техникой":          "Cu aparate",
	"Техника включена":   "Tehnică inclusă",
	"Бытовая техника":    "Electrocasnice",

	// Heating & Climate
	"Автономное отопление": "Încălzire autonomă",
	"Независимое отопление": "Încălzire independentă",
	"Кондиционер":           "Aer condiționado",
	"Кондиционирование":     "Climatizare",
	"Климат-контроль":       "Control climatic",
	"Теплые полы":           "Încălzire în pardoseală",
	"Подогрев пола":         "Pardoseală caldă",
	"Напольное отопление":   "Încălzire prin pardoseală",

	// Windows & Doors
	"Стеклопакет":         "Termopan",
	"Стеклопакеты":        "Geamuri termopan",
	"Пластиковые окна":    "Ferestre termopan",
	"Панорамные окна":     "Geamuri panoramice",
	"Большие окна":        "Ferestre panoramice",
	"Бронированная дверь": "Ușă blindată",
	"Металлическая дверь": "Ușă metalică",
	"Дверь безопасности":  "Ușă de securitate",

	// Flooring
	"Паркет":  "Parchet",
	"Ламинат": "Laminat",

	// Communication & Security
	"Телефонная линия":     "Linie telefonică",
	"Стационарный телефон": "Telefon fix",
	"Система умный дом":    "Sistem casă inteligentă",
	"Умный дом":            "Smart home",
	"Автоматизация":        "Automatizare",
	"Домофон":              "Interfon",
	"Интернет":             "Internet",
	"Интернет-соединение":  "Conexiune internet",
	"ТВ кабель":            "Cablu TV",
	"Кабельное ТВ":         "Televiziune prin cablu",
	"Телевидение":          "TV prin cablu",
	"Сигнализация":         "Sistem de alarmă",
	"Система безопасности": "Alarmă",
	"Видеонаблюдение":      "Supraveghere video",
	"Камеры наблюдения":    "Camere de supraveghere",

	// Building Amenities
	"Лифт":             "Ascensor",
	"Детская площадка": "Teren de joacă",
	"Игровая площадка": "Loc de joacă pentru copii",

	// Property Characteristics
	"Автор объявления":     "Autorul anunțului",
	"Количество комнат":    "Număr de camere",
	"Общая площадь":        "Suprafață totală",
	"Жилая площадь":        "Suprafață locuibilă",
	"Площадь кухни":        "Suprafață bucătărie",
	"Жилой фонд":           "Fond locativ",
	"Этаж":                 "Etaj",
	"Количество этажей":    "Număr de etaje",
	"Застройщик":           "Dezvoltator",
	"Тип здания":           "Tip clădire",
	"Состояние квартиры":   "Starea apartamentului",
	"Планировка":           "Compartimentare",
	"Тип планировки":       "Tipul de plan",
	"Количество санузлов":  "Număr de băi",
	"Количество балконов":  "Număr de balcoane",
	"Высота потолка":       "Înălțimea tavanului",
	"Тип парковки":         "Tipul de parcare",
	"Парковка":             "Parcare",
	"Гостиная":             "Living",
	"Санузел":              "Grup sanitar",
	"Балкон":               "Balcon/ lojie",
	"Высота потолков":      "Înălțimea tavanelor",
	"Парковочное место":    "Loc de parcare",

	// Property Characteristic Values
	"Агентство":               "Agenție",
	"Собственник":             "Proprietar",
	"Новостройка":             "Construcție nouă",
	"Вторичный":               "Secundar",
	"Евроремонт":              "Reparație euro",
	"Требует ремонт":          "Necesită reparație",
	"Белая":                   "Alb",
	"Белый вариант":           "Varianta albă",
	"Старый тип":              "De tip vechi",
	"Улучшенная":              "Îmbunătățită",
	"Свободная":               "Liberă",
	"Гараж":                   "Garaj",
	"Подземная":               "Subteran",
	"Подземная парковка":      "Subterană",
	"Уличная":                 "Stradă",
	"Застройщик недвижимости": "Dezvoltator imobiliar",
	"Квартира с 2 комнатами":  "Apartament cu 2 camere",
	"Квартира с гостиной":     "Apartament cu living",
	"Новостройки":             "Construcții noi",
	"Индивидуальная":          "Individuală",
	"Variantă albă":           "Variantă albă",
	"Открытая":                "Deschis",
	"Нет":                     "Nu",
	"Да":                      "Da",

	// Feature Section Headers
	"Характеристики": "Caracteristici",
	"Особенности":    "Particularități",
	"Удобства":       "Facilități",
	"Коммуникации":   "Comunicații",
	"Безопасность":   "Securitate",
	"Отопление":      "Încălzire",
	"Состояние":      "Stare",
}

// StreetNameTranslations maps Russian street names and common abbreviations to Romanian.
var StreetNameTranslations = map[string]string{
	// Common Chișinău streets
	"Николай Зелински":    "Nicolae Zelinski",
	"Зелински":            "Zelinski",
	"Иона Крянгэ":         "Iona Creangă",
	"Крянгэ":              "Creangă",
	"Михаил Когэлничану":  "Mihail Kogălniceanu",
	"Когэлничану":         "Kogălniceanu",
	"Андрей Лупан":        "Andrei Lupan",
	"Лупан":               "Lupan",
	"Александр Пушкин":    "Alexandr Pușkin",
	"Пушкин":              "Pușkin",
	"Ион Лука Караджале":  "Ion Luca Caragiale",
	"Караджале":           "Caragiale",
	"Константин Брынкуш":  "Constantin Brâncuși",
	"Брынкуш":             "Brâncuși",
	"Штефан Великий":      "Ștefan cel Mare",
	"Великий":             "cel Mare",
	"Василий Алехандри":   "Vasile Alecsandri",
	"Алехандри":           "Alecsandri",
	"Михаил Еминеску":     "Mihai Eminescu",
	"Еминеску":            "Eminescu",
	"Григорий Виеру":      "Grigore Vieru",
	"Виеру":               "Vieru",

	// Common prefixes
	"ул. ":     "strada ",
	"улица ":   "strada ",
	"бул. ":    "bulevardul ",
	"бульвар ": "bulevardul ",
	"пр. ":     "prospektul ",
	"проспект ": "prospektul ",
	"пл. ":     "piața ",
	"площадь ": "piața ",
}

// RomanianToRussianFeatures is the reverse mapping of PropertyFeatureTranslations.
var RomanianToRussianFeatures = make(map[string]string)

func init() {
	for k, v := range PropertyFeatureTranslations {
		RomanianToRussianFeatures[v] = k
	}
}

// DetectCyrillic checks if a string contains Cyrillic characters.
func DetectCyrillic(text string) bool {
	cyrillicPattern := regexp.MustCompile(`[\u0400-\u04FF]`)
	return cyrillicPattern.MatchString(text)
}

// TranslateRussianToRomanian translates Russian street names/features to Romanian.
func TranslateRussianToRomanian(text string) string {
	if text == "" || !DetectCyrillic(text) {
		return text
	}

	translated := text
	// Sort keys by length in descending order to avoid prefix conflicts
	keys := make([]string, 0, len(StreetNameTranslations))
	for k := range StreetNameTranslations {
		keys = append(keys, k)
	}

	// Simple sorting by length descending
	for i := 0; i < len(keys); i++ {
		for j := i + 1; j < len(keys); j++ {
			if len(keys[i]) < len(keys[j]) {
				keys[i], keys[j] = keys[j], keys[i]
			}
		}
	}

	// Apply street translations
	for _, key := range keys {
		val := StreetNameTranslations[key]
		re := regexp.MustCompile("(?i)" + regexp.QuoteMeta(key))
		translated = re.ReplaceAllString(translated, val)
	}

	// Split and translate word-by-word for other Cyrillic terms if any
	words := regexp.MustCompile(`([,\s\.\-]+)`).Split(translated, -1)
	delims := regexp.MustCompile(`([,\s\.\-]+)`).FindAllString(translated, -1)
	
	var finalParts []string
	for idx, word := range words {
		if DetectCyrillic(word) {
			wordClean := strings.Trim(word, ".,- ")
			translatedWord := word
			
			// Look for feature translations
			for k, v := range PropertyFeatureTranslations {
				if strings.EqualFold(k, wordClean) {
					translatedWord = strings.Replace(word, wordClean, v, 1)
					break
				}
			}
			finalParts = append(finalParts, translatedWord)
		} else {
			finalParts = append(finalParts, word)
		}
		if idx < len(delims) {
			finalParts = append(finalParts, delims[idx])
		}
	}

	return strings.Join(finalParts, "")
}

// TranslateFeature translates a feature key or value from Russian to Romanian or vice-versa.
func TranslateFeature(text string, toRomanian bool) string {
	if toRomanian {
		if val, ok := PropertyFeatureTranslations[text]; ok {
			return val
		}
		return text
	} else {
		if val, ok := RomanianToRussianFeatures[text]; ok {
			return val
		}
		return text
	}
}
