package main

import (
	"net"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type SensitiveCatalogEntry struct {
	Classification string
	Family         string
	Category       string
	Sensitivity    string
	BaseConfidence int
	Frameworks     []string
	DetectionMode  string
}

var sensitiveDataCatalog = map[string]SensitiveCatalogEntry{
	"CPF": {Classification: "CPF", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 75, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "checksum"},
	"CPF_LIKE": {Classification: "CPF_LIKE", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 60, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "fuzzy_context"},
	"CNPJ": {Classification: "CNPJ", Family: "business_data", Category: "business_identifier", Sensitivity: "moderate", BaseConfidence: 75, Frameworks: []string{"BUSINESS_DATA"}, DetectionMode: "checksum"},
	"RG_BR": {Classification: "RG_BR", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 65, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "pattern_context"},
	"CNH_BR": {Classification: "CNH_BR", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 80, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"PIS_NIS_BR": {Classification: "PIS_NIS_BR", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 80, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"VOTER_ID_BR": {Classification: "VOTER_ID_BR", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 80, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"CNS_BR": {Classification: "CNS_BR", Family: "sensitive_personal", Category: "health_identifier", Sensitivity: "restricted", BaseConfidence: 80, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL", "NIST_PII"}, DetectionMode: "context"},
	"PASSPORT": {Classification: "PASSPORT", Family: "pii", Category: "government_id", Sensitivity: "high", BaseConfidence: 75, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"FULL_NAME": {Classification: "FULL_NAME", Family: "pii", Category: "identity", Sensitivity: "moderate", BaseConfidence: 70, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"EMAIL_ADDRESS": {Classification: "EMAIL_ADDRESS", Family: "pii", Category: "contact", Sensitivity: "moderate", BaseConfidence: 70, Frameworks: []string{"LGPD", "NIST_PII", "GDPR"}, DetectionMode: "pattern"},
	"PHONE_BR": {Classification: "PHONE_BR", Family: "pii", Category: "contact", Sensitivity: "moderate", BaseConfidence: 65, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "formatted_pattern"},
	"DATE_OF_BIRTH": {Classification: "DATE_OF_BIRTH", Family: "pii", Category: "identity_attribute", Sensitivity: "moderate", BaseConfidence: 80, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"PHYSICAL_ADDRESS": {Classification: "PHYSICAL_ADDRESS", Family: "pii", Category: "contact", Sensitivity: "moderate", BaseConfidence: 70, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "address_pattern"},
	"IP_ADDRESS": {Classification: "IP_ADDRESS", Family: "linkable_data", Category: "online_identifier", Sensitivity: "moderate", BaseConfidence: 65, Frameworks: []string{"GDPR", "NIST_PII"}, DetectionMode: "context"},
	"MAC_ADDRESS": {Classification: "MAC_ADDRESS", Family: "linkable_data", Category: "device_identifier", Sensitivity: "moderate", BaseConfidence: 70, Frameworks: []string{"NIST_PII"}, DetectionMode: "context"},
	"IMEI": {Classification: "IMEI", Family: "linkable_data", Category: "device_identifier", Sensitivity: "moderate", BaseConfidence: 80, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context_checksum"},
	"VEHICLE_PLATE_BR": {Classification: "VEHICLE_PLATE_BR", Family: "linkable_data", Category: "vehicle_identifier", Sensitivity: "moderate", BaseConfidence: 65, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "pattern_context"},
	"GEOLOCATION": {Classification: "GEOLOCATION", Family: "pii", Category: "location", Sensitivity: "high", BaseConfidence: 80, Frameworks: []string{"LGPD", "NIST_PII", "GDPR"}, DetectionMode: "context"},
	"EMPLOYEE_ID": {Classification: "EMPLOYEE_ID", Family: "linkable_data", Category: "employment", Sensitivity: "moderate", BaseConfidence: 75, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"STUDENT_ID": {Classification: "STUDENT_ID", Family: "linkable_data", Category: "education", Sensitivity: "moderate", BaseConfidence: 75, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"HEALTH_RECORD_ID": {Classification: "HEALTH_RECORD_ID", Family: "sensitive_personal", Category: "health", Sensitivity: "restricted", BaseConfidence: 85, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL", "NIST_PII"}, DetectionMode: "context"},
	"HEALTH_DATA": {Classification: "HEALTH_DATA", Family: "sensitive_personal", Category: "health", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL", "NIST_PII"}, DetectionMode: "semantic_required"},
	"BIOMETRIC_DATA": {Classification: "BIOMETRIC_DATA", Family: "sensitive_personal", Category: "biometric", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_or_specialized_required"},
	"GENETIC_DATA": {Classification: "GENETIC_DATA", Family: "sensitive_personal", Category: "genetic", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_required"},
	"RACIAL_ETHNIC_DATA": {Classification: "RACIAL_ETHNIC_DATA", Family: "sensitive_personal", Category: "protected_attribute", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_required"},
	"RELIGIOUS_BELIEF": {Classification: "RELIGIOUS_BELIEF", Family: "sensitive_personal", Category: "protected_attribute", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_required"},
	"POLITICAL_OPINION": {Classification: "POLITICAL_OPINION", Family: "sensitive_personal", Category: "protected_attribute", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_required"},
	"TRADE_UNION_MEMBERSHIP": {Classification: "TRADE_UNION_MEMBERSHIP", Family: "sensitive_personal", Category: "protected_attribute", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_required"},
	"SEX_LIFE_OR_ORIENTATION": {Classification: "SEX_LIFE_OR_ORIENTATION", Family: "sensitive_personal", Category: "protected_attribute", Sensitivity: "restricted", BaseConfidence: 0, Frameworks: []string{"LGPD_SENSITIVE", "GDPR_SPECIAL"}, DetectionMode: "semantic_required"},
	"BANK_ACCOUNT": {Classification: "BANK_ACCOUNT", Family: "financial", Category: "banking", Sensitivity: "high", BaseConfidence: 75, Frameworks: []string{"NIST_PII", "LGPD"}, DetectionMode: "context"},
	"PIX_KEY": {Classification: "PIX_KEY", Family: "financial", Category: "payment_identifier", Sensitivity: "high", BaseConfidence: 75, Frameworks: []string{"LGPD", "NIST_PII"}, DetectionMode: "context"},
	"CREDIT_CARD": {Classification: "CREDIT_CARD", Family: "payment_card", Category: "pan", Sensitivity: "restricted", BaseConfidence: 75, Frameworks: []string{"PCI_DSS", "NIST_PII"}, DetectionMode: "luhn_checksum"},
	"CARD_SECURITY_CODE": {Classification: "CARD_SECURITY_CODE", Family: "payment_card", Category: "sensitive_authentication_data", Sensitivity: "restricted", BaseConfidence: 90, Frameworks: []string{"PCI_DSS_SAD"}, DetectionMode: "context"},
	"CARD_PIN": {Classification: "CARD_PIN", Family: "payment_card", Category: "sensitive_authentication_data", Sensitivity: "restricted", BaseConfidence: 90, Frameworks: []string{"PCI_DSS_SAD"}, DetectionMode: "context"},
	"CARD_TRACK_DATA": {Classification: "CARD_TRACK_DATA", Family: "payment_card", Category: "sensitive_authentication_data", Sensitivity: "restricted", BaseConfidence: 95, Frameworks: []string{"PCI_DSS_SAD"}, DetectionMode: "track_pattern"},
	"SECRET": {Classification: "SECRET", Family: "credential_secret", Category: "secret", Sensitivity: "restricted", BaseConfidence: 90, Frameworks: []string{"SECURITY_SECRET"}, DetectionMode: "provider_pattern_or_context"},
	"CREDENTIAL": {Classification: "CREDENTIAL", Family: "credential_secret", Category: "authentication", Sensitivity: "restricted", BaseConfidence: 90, Frameworks: []string{"SECURITY_SECRET"}, DetectionMode: "context"},
}

var (
	rgFormattedRegex = regexp.MustCompile(`\b[0-9]{1,2}\.[0-9]{3}\.[0-9]{3}-[0-9Xx]\b`)
	phoneBRRegex = regexp.MustCompile(`(?:\+?55[\s.-]?)?(?:\([1-9][0-9]\)|[1-9][0-9])[\s.-]?(?:9[0-9]{4}|[2-5][0-9]{3})[\s.-]?[0-9]{4}`)
	dobContextRegex = regexp.MustCompile(`(?i)(?:data\s+de\s+nascimento|nascimento|date\s+of\s+birth|birth\s+date|fecha\s+de\s+nacimiento|nacido(?:a)?\s+em)\s*[:#=-]?\s*([0-3]?[0-9][/\-.][01]?[0-9][/\-.](?:19|20)[0-9]{2})`)
	fullNameContextRegex = regexp.MustCompile(`(?i)(?:nome(?:\s+completo)?|full\s+name|nombre(?:\s+completo)?)\s*[:#=-]?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]+){1,5})`)
	addressBRRegex = regexp.MustCompile(`(?i)\b(?:rua|r\.|avenida|av\.|travessa|alameda|estrada|rodovia|praça|praca)\s+[A-Za-zÀ-ÿ0-9'’.\- ]{2,80}(?:,\s*|\s+n[ºo°]?\s*)[0-9]{1,6}[A-Za-z]?\b`)
	ipContextRegex = regexp.MustCompile(`(?i)(?:\bip\b|end[eê]re[cç]o\s+ip|ip\s+address|client_ip|remote_addr)\s*[:#=-]?\s*((?:[0-9]{1,3}\.){3}[0-9]{1,3})`)
	macContextRegex = regexp.MustCompile(`(?i)(?:mac(?:\s+address)?|bssid|endere[cç]o\s+mac)\s*[:#=-]?\s*([0-9A-Fa-f]{2}(?:(?:[:-])[0-9A-Fa-f]{2}){5})`)
	imeiContextRegex = regexp.MustCompile(`(?i)\bIMEI\s*[:#=-]?\s*([0-9]{15})\b`)
	oldPlateRegex = regexp.MustCompile(`\b[A-Z]{3}-[0-9]{4}\b`)
	mercosulPlateContextRegex = regexp.MustCompile(`(?i)(?:placa|license\s+plate|matr[ií]cula\s+veicular)\s*[:#=-]?\s*([A-Z]{3}[0-9][A-Z][0-9]{2})\b`)
	geoContextRegex = regexp.MustCompile(`(?i)(?:gps|geolocaliza[cç][aã]o|geolocation|latitude)[^0-9+\-]{0,20}([+\-]?[0-9]{1,2}(?:\.[0-9]+)?)\s*[,;/]\s*([+\-]?[0-9]{1,3}(?:\.[0-9]+)?)`)
	cnhContextRegex = regexp.MustCompile(`(?i)(?:\bCNH\b|carteira\s+nacional\s+de\s+habilita[cç][aã]o|driver'?s?\s+license)\s*[:#=-]?\s*([0-9]{11})\b`)
	pisContextRegex = regexp.MustCompile(`(?i)(?:\bPIS\b|\bPASEP\b|\bNIS\b)\s*[:#=-]?\s*([0-9]{3}[.\s-]?[0-9]{5}[.\s-]?[0-9]{2}[-\s]?[0-9])\b`)
	voterContextRegex = regexp.MustCompile(`(?i)(?:t[ií]tulo\s+de\s+eleitor|voter\s+id)\s*[:#=-]?\s*([0-9]{12})\b`)
	cnsContextRegex = regexp.MustCompile(`(?i)(?:\bCNS\b|cart[aã]o\s+nacional\s+de\s+sa[uú]de|sus\s+card)\s*[:#=-]?\s*([0-9]{15})\b`)
	employeeIDContextRegex = regexp.MustCompile(`(?i)(?:matr[ií]cula\s+(?:funcional|empregado|funcion[aá]rio)|employee\s+id|employee\s+number)\s*[:#=-]?\s*([A-Za-z0-9._/-]{3,40})`)
	studentIDContextRegex = regexp.MustCompile(`(?i)(?:matr[ií]cula\s+(?:acad[eê]mica|aluno)|student\s+id|student\s+number)\s*[:#=-]?\s*([A-Za-z0-9._/-]{3,40})`)
	healthRecordContextRegex = regexp.MustCompile(`(?i)(?:prontu[aá]rio|medical\s+record|registro\s+m[eé]dico|patient\s+id)\s*[:#=-]?\s*([A-Za-z0-9._/-]{3,40})`)
	cardSecurityCodeRegex = regexp.MustCompile(`(?i)(?:\bCVV2?\b|\bCVC2?\b|\bCID\b|c[oó]digo\s+de\s+seguran[cç]a)\s*[:#=-]?\s*([0-9]{3,4})\b`)
	cardPINRegex = regexp.MustCompile(`(?i)(?:\bPIN\b|senha\s+do\s+cart[aã]o|card\s+pin)\s*[:#=-]?\s*([0-9]{4,12})\b`)
	track1Regex = regexp.MustCompile(`%B([0-9]{13,19})\^[^^]{2,40}\^[0-9]{4}`)
	track2Regex = regexp.MustCompile(`;([0-9]{13,19})=[0-9]{4,}`)
)

func catalogEntry(classification string) (SensitiveCatalogEntry, bool) {
	entry, ok := sensitiveDataCatalog[strings.ToUpper(strings.TrimSpace(classification))]
	return entry, ok
}

func catalogConfidence(d Detection) int {
	entry, ok := catalogEntry(d.Classification)
	if !ok {
		return 50
	}
	score := entry.BaseConfidence
	evidence := strings.ToLower(d.Evidence)
	if strings.Contains(evidence, "checksum") || strings.Contains(evidence, "luhn") {
		if score < 75 {
			score = 75
		}
	}
	if strings.Contains(evidence, "context") {
		score += 10
	}
	if strings.Contains(evidence, "formatted_pattern") {
		score += 5
	}
	if strings.Contains(evidence, "track_pattern") || strings.Contains(evidence, "private_key_marker") {
		if score < 90 {
			score = 90
		}
	}
	if strings.Contains(evidence, "fuzzy") || strings.Contains(evidence, "malformed") {
		score -= 10
	}
	if score > 95 {
		score = 95
	}
	if score < 0 {
		score = 0
	}
	return score
}

func confidenceBand(score int) string {
	switch {
	case score >= 85:
		return "high"
	case score >= 75:
		return "medium"
	default:
		return "low"
	}
}

func sensitiveCatalogTags(d Detection) []string {
	entry, ok := catalogEntry(d.Classification)
	if !ok {
		return nil
	}
	tags := []string{
		"data_family:" + entry.Family,
		"data_category:" + entry.Category,
		"sensitivity:" + entry.Sensitivity,
		"confidence:" + confidenceBand(catalogConfidence(d)),
	}
	for _, framework := range entry.Frameworks {
		tags = append(tags, "framework:"+strings.ToLower(framework))
	}
	return tags
}

func catalogAggregateTags(detections []Detection) []string {
	hasDirectIdentity := false
	hasSpecial := false
	hasPAN := false
	hasSAD := false
	weakPII := map[string]bool{}

	for _, d := range detections {
		class := strings.ToUpper(strings.TrimSpace(d.Classification))
		entry, ok := catalogEntry(class)
		if !ok {
			continue
		}
		if entry.Category == "government_id" || entry.Category == "health_identifier" {
			hasDirectIdentity = true
		}
		if entry.Family == "sensitive_personal" {
			hasSpecial = true
		}
		if class == "CREDIT_CARD" {
			hasPAN = true
		}
		if class == "CARD_SECURITY_CODE" || class == "CARD_PIN" || class == "CARD_TRACK_DATA" {
			hasSAD = true
		}
		switch class {
		case "FULL_NAME", "EMAIL_ADDRESS", "PHONE_BR", "DATE_OF_BIRTH", "PHYSICAL_ADDRESS",
			"IP_ADDRESS", "MAC_ADDRESS", "IMEI", "VEHICLE_PLATE_BR", "GEOLOCATION",
			"EMPLOYEE_ID", "STUDENT_ID":
			weakPII[class] = true
		}
	}

	tags := []string{}
	if len(weakPII) >= 2 {
		tags = append(tags, "pii_bundle")
	}
	if len(weakPII) >= 3 {
		tags = append(tags, "pii_profile")
	}
	if hasSpecial && hasDirectIdentity {
		tags = append(tags, "special_category_linked_identity")
	}
	if hasPAN && hasSAD {
		tags = append(tags, "pci_account_plus_authentication")
	}
	return tags
}

func validBRPhone(value string) bool {
	n := digits(value)
	if strings.HasPrefix(n, "55") && len(n) >= 12 {
		n = n[2:]
	}
	if len(n) != 10 && len(n) != 11 {
		return false
	}
	if n[0] == '0' || n[1] == '0' {
		return false
	}
	if len(n) == 11 && n[2] != '9' {
		return false
	}
	return true
}

func validDateBR(value string) bool {
	normalized := strings.NewReplacer(".", "/", "-", "/").Replace(strings.TrimSpace(value))
	if _, err := time.Parse("02/01/2006", normalized); err == nil {
		return true
	}
	_, err := time.Parse("2/1/2006", normalized)
	return err == nil
}

func validLatLong(latRaw, longRaw string) bool {
	lat, err := strconv.ParseFloat(latRaw, 64)
	if err != nil || lat < -90 || lat > 90 {
		return false
	}
	lon, err := strconv.ParseFloat(longRaw, 64)
	return err == nil && lon >= -180 && lon <= 180
}

func augmentSensitiveCatalogDetections(text string, current []Detection) []Detection {
	out := append([]Detection(nil), current...)
	seen := map[string]bool{}
	for _, d := range out {
		seen[strings.ToUpper(d.Classification)+"|"+fingerprint(d.Value)] = true
	}
	add := func(classification, value, evidence string) {
		value = strings.TrimSpace(value)
		if value == "" {
			return
		}
		key := strings.ToUpper(classification) + "|" + fingerprint(value)
		if seen[key] {
			return
		}
		seen[key] = true
		out = append(out, Detection{
			Classification: strings.ToUpper(classification),
			Value: value,
			Evidence: evidence,
		})
	}

	for _, value := range rgFormattedRegex.FindAllString(text, 100) {
		add("RG_BR", value, "rg_formatted_pattern")
	}
	for _, value := range phoneBRRegex.FindAllString(text, 100) {
		if validBRPhone(value) {
			add("PHONE_BR", value, "phone_br_formatted_pattern")
		}
	}
	for _, value := range captureMatches(dobContextRegex, text, 1, 100) {
		if validDateBR(value) {
			add("DATE_OF_BIRTH", value, "date_of_birth_context")
		}
	}
	for _, value := range captureMatches(fullNameContextRegex, text, 1, 100) {
		add("FULL_NAME", value, "full_name_context")
	}
	for _, value := range addressBRRegex.FindAllString(text, 100) {
		add("PHYSICAL_ADDRESS", value, "physical_address_pattern")
	}
	for _, value := range captureMatches(ipContextRegex, text, 1, 100) {
		if ip := net.ParseIP(value); ip != nil && ip.To4() != nil {
			add("IP_ADDRESS", value, "ip_address_context")
		}
	}
	for _, value := range captureMatches(macContextRegex, text, 1, 100) {
		add("MAC_ADDRESS", value, "mac_address_context")
	}
	for _, value := range captureMatches(imeiContextRegex, text, 1, 100) {
		if validLuhn(value) {
			add("IMEI", value, "imei_context_luhn_checksum")
		}
	}
	for _, value := range oldPlateRegex.FindAllString(strings.ToUpper(text), 100) {
		add("VEHICLE_PLATE_BR", value, "vehicle_plate_formatted_pattern")
	}
	for _, value := range captureMatches(mercosulPlateContextRegex, strings.ToUpper(text), 1, 100) {
		add("VEHICLE_PLATE_BR", value, "vehicle_plate_context")
	}
	for _, match := range geoContextRegex.FindAllStringSubmatch(text, 100) {
		if len(match) >= 3 && validLatLong(match[1], match[2]) {
			add("GEOLOCATION", match[1]+","+match[2], "geolocation_context")
		}
	}
	for _, value := range captureMatches(cnhContextRegex, text, 1, 100) {
		add("CNH_BR", value, "cnh_context")
	}
	for _, value := range captureMatches(pisContextRegex, text, 1, 100) {
		add("PIS_NIS_BR", value, "pis_nis_context")
	}
	for _, value := range captureMatches(voterContextRegex, text, 1, 100) {
		add("VOTER_ID_BR", value, "voter_id_context")
	}
	for _, value := range captureMatches(cnsContextRegex, text, 1, 100) {
		add("CNS_BR", value, "cns_health_identifier_context")
	}
	for _, value := range captureMatches(employeeIDContextRegex, text, 1, 100) {
		add("EMPLOYEE_ID", value, "employee_id_context")
	}
	for _, value := range captureMatches(studentIDContextRegex, text, 1, 100) {
		add("STUDENT_ID", value, "student_id_context")
	}
	for _, value := range captureMatches(healthRecordContextRegex, text, 1, 100) {
		add("HEALTH_RECORD_ID", value, "health_record_context")
	}
	for _, value := range captureMatches(cardSecurityCodeRegex, text, 1, 100) {
		add("CARD_SECURITY_CODE", value, "pci_sad_security_code_context")
	}
	for _, value := range captureMatches(cardPINRegex, text, 1, 100) {
		add("CARD_PIN", value, "pci_sad_pin_context")
	}
	for _, match := range track1Regex.FindAllStringSubmatch(text, 100) {
		if len(match) > 1 && validLuhn(match[1]) {
			add("CARD_TRACK_DATA", match[0], "pci_sad_track_pattern")
		}
	}
	for _, match := range track2Regex.FindAllStringSubmatch(text, 100) {
		if len(match) > 1 && validLuhn(match[1]) {
			add("CARD_TRACK_DATA", match[0], "pci_sad_track_pattern")
		}
	}
	return out
}
