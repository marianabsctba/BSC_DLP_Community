package main

import (
	"regexp"
	"strings"
)

type Detection struct {
	Classification string
	Value          string
	Evidence       string
}

type CustomDetectionRule struct {
	ID             int    `json:"id"`
	Name           string `json:"name"`
	Classification string `json:"classification"`
	Pattern        string `json:"pattern"`
	Enabled        bool   `json:"enabled"`
}

var cnpjRegex = regexp.MustCompile(`\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}`)
var cardRegex = regexp.MustCompile(`(?:\d[ -]?){13,19}`)
var emailRegex = regexp.MustCompile(`[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}`)
var awsKeyRegex = regexp.MustCompile(`AKIA[0-9A-Z]{16}`)
var privateKeyRegex = regexp.MustCompile(`-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----`)
var githubTokenRegex = regexp.MustCompile(`gh[pousr]_[A-Za-z0-9]{20,255}`)
var googleAPIKeyRegex = regexp.MustCompile(`AIza[0-9A-Za-z\-_]{35}`)
var slackTokenRegex = regexp.MustCompile(`xox[baprs]-[0-9A-Za-z-]{10,}`)
var jwtRegex = regexp.MustCompile(`eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}`)
var passwordAssignRegex = regexp.MustCompile(`(?i)(?:password|passwd|pwd|senha)\s*[:=]\s*["']?([^\s"';,]{6,128})`)
var secretAssignRegex = regexp.MustCompile(`(?i)(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key|client[_ -]?secret)\s*[:=]\s*["']?([A-Za-z0-9_\-./+=]{8,256})`)
var bearerRegex = regexp.MustCompile(`(?i)\bbearer\s+([A-Za-z0-9_\-./+=]{12,512})`)

// Context-based Brazilian PII patterns intentionally require a nearby label to
// reduce false positives in logs and arbitrary numeric content.
var rgContextRegex = regexp.MustCompile(`(?i)\bRG\s*[:#-]?\s*([0-9]{1,2}[.]?[0-9]{3}[.]?[0-9]{3}[-]?[0-9Xx])`)
var phoneContextRegex = regexp.MustCompile(`(?i)(?:telefone|fone|celular|mobile|whatsapp|contato)\s*[:#-]?\s*((?:\+?55\s*)?\(?[1-9][0-9]\)?[\s.-]?(?:9?[0-9]{4})[\s.-]?[0-9]{4})`)
var pixContextRegex = regexp.MustCompile(`(?i)(?:chave\s+pix|pix)\s*[:#=-]?\s*([A-Za-z0-9@._+\-]{5,140})`)
var bankContextRegex = regexp.MustCompile(`(?i)(?:ag[eê]ncia\s*[:#-]?\s*[0-9]{1,6}[-0-9]*\s*(?:[,;/]|e)?\s*)?conta\s*[:#-]?\s*([0-9]{2,20}[-]?[0-9Xx]?)`)
var passportContextRegex = regexp.MustCompile(`(?i)(?:passaporte|passport)\s*[:#-]?\s*([A-Z]{1,2}[0-9]{6,8})`)

func validCNPJ(v string) bool {
	n := digits(v)
	if len(n) != 14 {
		return false
	}
	allSame := true
	for i := 1; i < len(n); i++ {
		if n[i] != n[0] {
			allSame = false
			break
		}
	}
	if allSame {
		return false
	}
	calc := func(base string, weights []int) int {
		sum := 0
		for i, w := range weights {
			sum += int(base[i]-'0') * w
		}
		r := sum % 11
		if r < 2 {
			return 0
		}
		return 11 - r
	}
	d1 := calc(n[:12], []int{5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2})
	if d1 != int(n[12]-'0') {
		return false
	}
	d2 := calc(n[:13], []int{6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2})
	return d2 == int(n[13]-'0')
}

func validLuhn(v string) bool {
	n := digits(v)
	if len(n) < 13 || len(n) > 19 {
		return false
	}
	sum := 0
	parity := len(n) % 2
	for i := 0; i < len(n); i++ {
		d := int(n[i] - '0')
		if i%2 == parity {
			d *= 2
			if d > 9 {
				d -= 9
			}
		}
		sum += d
	}
	return sum%10 == 0
}

func captureMatches(re *regexp.Regexp, text string, group int, limit int) []string {
	all := re.FindAllStringSubmatch(text, limit)
	out := make([]string, 0, len(all))
	for _, match := range all {
		if group >= 0 && group < len(match) && strings.TrimSpace(match[group]) != "" {
			out = append(out, strings.TrimSpace(match[group]))
		}
	}
	return out
}

func detectSensitive(text string) []Detection {
	out := []Detection{}
	seen := map[string]bool{}
	add := func(classification, value, evidence string) {
		value = strings.TrimSpace(value)
		if value == "" {
			return
		}
		key := classification + "|" + fingerprint(value)
		if seen[key] {
			return
		}
		seen[key] = true
		out = append(out, Detection{classification, value, evidence})
	}

	for _, value := range cpfRegex.FindAllString(text, 100) {
		if validCPF(value) {
			add("CPF", value, "cpf_checksum")
		}
	}
	for _, value := range cnpjRegex.FindAllString(text, 100) {
		if validCNPJ(value) {
			add("CNPJ", value, "cnpj_checksum")
		}
	}
	for _, value := range cardRegex.FindAllString(text, 100) {
		compact := digits(value)
		if validLuhn(compact) {
			add("CREDIT_CARD", compact, "luhn_checksum")
		}
	}
	for _, value := range emailRegex.FindAllString(text, 100) {
		add("EMAIL_ADDRESS", value, "email_pattern")
	}
	for _, value := range captureMatches(rgContextRegex, text, 1, 100) {
		add("RG_BR", value, "rg_context")
	}
	for _, value := range captureMatches(phoneContextRegex, text, 1, 100) {
		add("PHONE_BR", value, "phone_context")
	}
	for _, value := range captureMatches(pixContextRegex, text, 1, 100) {
		add("PIX_KEY", value, "pix_context")
	}
	for _, value := range captureMatches(bankContextRegex, text, 1, 100) {
		add("BANK_ACCOUNT", value, "bank_account_context")
	}
	for _, value := range captureMatches(passportContextRegex, text, 1, 100) {
		add("PASSPORT", value, "passport_context")
	}

	for _, value := range awsKeyRegex.FindAllString(text, 100) {
		add("SECRET", value, "aws_access_key_pattern")
	}
	for _, value := range githubTokenRegex.FindAllString(text, 100) {
		add("SECRET", value, "github_token_pattern")
	}
	for _, value := range googleAPIKeyRegex.FindAllString(text, 100) {
		add("SECRET", value, "google_api_key_pattern")
	}
	for _, value := range slackTokenRegex.FindAllString(text, 100) {
		add("SECRET", value, "slack_token_pattern")
	}
	for _, value := range jwtRegex.FindAllString(text, 100) {
		add("SECRET", value, "jwt_pattern")
	}
	for _, value := range captureMatches(secretAssignRegex, text, 1, 100) {
		add("SECRET", value, "secret_assignment_context")
	}
	for _, value := range captureMatches(passwordAssignRegex, text, 1, 100) {
		add("CREDENTIAL", value, "password_assignment_context")
	}
	for _, value := range captureMatches(bearerRegex, text, 1, 100) {
		add("CREDENTIAL", value, "bearer_token_context")
	}
	if privateKeyRegex.MatchString(text) {
		add("SECRET", "PRIVATE_KEY_MATERIAL", "private_key_marker")
	}

	return out
}

func detectSensitiveWithRules(text string, rules []CustomDetectionRule) []Detection {
	out := detectSensitive(text)
	seen := map[string]bool{}
	for _, d := range out {
		seen[d.Classification+"|"+fingerprint(d.Value)] = true
	}
	for _, rule := range rules {
		if !rule.Enabled || strings.TrimSpace(rule.Pattern) == "" || strings.TrimSpace(rule.Classification) == "" {
			continue
		}
		re, err := regexp.Compile(rule.Pattern)
		if err != nil {
			continue
		}
		matches := re.FindAllString(text, 100)
		for _, value := range matches {
			classification := strings.ToUpper(strings.TrimSpace(rule.Classification))
			key := classification + "|" + fingerprint(value)
			if seen[key] {
				continue
			}
			seen[key] = true
			out = append(out, Detection{
				Classification: classification,
				Value:          value,
				Evidence:       "custom_rule:" + rule.Name,
			})
		}
	}
	return out
}
