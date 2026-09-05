package main

import (
	"regexp"
	"strings"
	"unicode"
)

type numericRun struct {
	Digits     string
	Start      int
	End        int
	Obfuscated bool
	Evasive    bool
}

var (
	evasionCPFLabelRegex  = regexp.MustCompile(`(?i)\bcpf\b`)
	evasionCNPJLabelRegex = regexp.MustCompile(`(?i)\bcnpj\b`)
	evasionCardLabelRegex = regexp.MustCompile(`(?i)\b(?:cart[aã]o|card|credit\s+card|cart[aã]o\s+de\s+cr[eé]dito)\b`)
	evasionWordTokenRegex = regexp.MustCompile(`(?i)[0-9]+|[\p{L}]+`)
)

var digitWordMap = map[string]byte{
	"zero": '0', "um": '1', "uma": '1', "dois": '2', "tres": '3',
	"quatro": '4', "cinco": '5', "seis": '6', "sete": '7', "oito": '8', "nove": '9',

	"one": '1', "two": '2', "three": '3', "four": '4', "five": '5',
	"six": '6', "seven": '7', "eight": '8', "nine": '9',

	"cero": '0', "uno": '1', "una": '1', "dos": '2', "cuatro": '4',
	"siete": '7', "ocho": '8', "nueve": '9',
}

var separatorWordSet = map[string]bool{
	"ponto": true, "punto": true, "dot": true,
	"traco": true, "hifen": true, "dash": true, "guion": true,
	"barra": true, "slash": true,
	"espaco": true, "space": true,
	"hash": true, "hashtag": true,
}

func foldDigitWord(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	replacer := strings.NewReplacer(
		"á", "a", "à", "a", "â", "a", "ã", "a",
		"é", "e", "ê", "e",
		"í", "i",
		"ó", "o", "ô", "o", "õ", "o",
		"ú", "u", "ü", "u",
		"ç", "c",
	)
	return replacer.Replace(value)
}

func digitRuneValue(r rune) (byte, bool, bool) {
	switch {
	case r >= '0' && r <= '9':
		return byte(r), true, false
	case r >= '\uFF10' && r <= '\uFF19':
		return byte('0' + (r - '\uFF10')), true, true
	case r >= '\u0660' && r <= '\u0669':
		return byte('0' + (r - '\u0660')), true, true
	case r >= '\u06F0' && r <= '\u06F9':
		return byte('0' + (r - '\u06F0')), true, true
	default:
		return 0, false, false
	}
}

func invisibleFormatRune(r rune) bool {
	switch r {
	case '\u200B', '\u200C', '\u200D', '\u2060', '\uFEFF':
		return true
	default:
		return false
	}
}

func allowedNumericSeparator(r rune) bool {
	return invisibleFormatRune(r) || unicode.IsSpace(r) || unicode.IsPunct(r) || unicode.IsSymbol(r)
}

func standardNumericSeparator(r rune) bool {
	switch r {
	case ' ', '\t', '.', '-', '/':
		return true
	default:
		return false
	}
}

func collectNumericRuns(text string) []numericRun {
	runes := []rune(text)
	out := []numericRun{}

	for i := 0; i < len(runes); {
		if _, ok, _ := digitRuneValue(runes[i]); !ok {
			i++
			continue
		}

		start := i
		var digitsBuilder strings.Builder
		totalSeparators := 0
		currentSeparatorRun := 0
		maxSeparatorRun := 0
		unusualSeparator := false
		evasive := false
		j := i

		for ; j < len(runes); j++ {
			if d, ok, unicodeDigit := digitRuneValue(runes[j]); ok {
				digitsBuilder.WriteByte(d)
				currentSeparatorRun = 0
				if unicodeDigit {
					evasive = true
				}
				if digitsBuilder.Len() > 40 {
					break
				}
				continue
			}

			if !allowedNumericSeparator(runes[j]) || digitsBuilder.Len() == 0 {
				break
			}

			currentSeparatorRun++
			totalSeparators++
			if currentSeparatorRun > maxSeparatorRun {
				maxSeparatorRun = currentSeparatorRun
			}
			if currentSeparatorRun > 8 {
				break
			}

			if invisibleFormatRune(runes[j]) {
				evasive = true
			}
			if runes[j] == '\n' || runes[j] == '\r' || !standardNumericSeparator(runes[j]) {
				unusualSeparator = true
			}
		}

		digitsValue := digitsBuilder.String()
		if len(digitsValue) >= 10 {
			obfuscated := unusualSeparator || maxSeparatorRun > 1 || totalSeparators > 4
			out = append(out, numericRun{
				Digits:     digitsValue,
				Start:      start,
				End:        j,
				Obfuscated: obfuscated,
				Evasive:    evasive,
			})
		}

		if j <= i {
			i++
		} else {
			i = j
		}
	}

	return out
}

func nearbyLabel(runes []rune, start int, kind string) bool {
	begin := start - 64
	if begin < 0 {
		begin = 0
	}
	prefix := strings.ToLower(string(runes[begin:start]))
	switch kind {
	case "cpf":
		return strings.Contains(prefix, "cpf")
	case "cnpj":
		return strings.Contains(prefix, "cnpj")
	case "card":
		return strings.Contains(prefix, "cartão") ||
			strings.Contains(prefix, "cartao") ||
			strings.Contains(prefix, "card") ||
			strings.Contains(prefix, "crédito") ||
			strings.Contains(prefix, "credito")
	default:
		return false
	}
}

func runEvidence(base string, run numericRun) string {
	parts := []string{base}
	if run.Obfuscated {
		parts = append(parts, "obfuscated_identifier")
	}
	if run.Evasive {
		parts = append(parts, "evasive_obfuscation")
	}
	return strings.Join(parts, "+")
}

func addUniqueDetection(out *[]Detection, seen map[string]bool, classification, value, evidence string) {
	classification = strings.ToUpper(strings.TrimSpace(classification))
	value = strings.TrimSpace(value)
	if classification == "" || value == "" {
		return
	}
	key := classification + "|" + fingerprint(value)
	if seen[key] {
		return
	}
	seen[key] = true
	*out = append(*out, Detection{
		Classification: classification,
		Value:          value,
		Evidence:       evidence,
	})
}

func validCPFWindow(value string) (string, bool) {
	if len(value) < 11 {
		return "", false
	}
	for i := 0; i+11 <= len(value); i++ {
		candidate := value[i : i+11]
		if validCPF(candidate) {
			return candidate, true
		}
	}
	return "", false
}

func parseDigitWords(segment string, maxDigits int) (string, bool) {
	tokens := evasionWordTokenRegex.FindAllString(segment, 48)
	var builder strings.Builder
	started := false
	usedWords := false
	skippedBefore := 0

	for _, token := range tokens {
		if builder.Len() >= maxDigits {
			break
		}

		if allASCIIDigits(token) {
			started = true
			for _, r := range token {
				if builder.Len() >= maxDigits {
					break
				}
				builder.WriteRune(r)
			}
			continue
		}

		folded := foldDigitWord(token)
		if d, ok := digitWordMap[folded]; ok {
			started = true
			usedWords = true
			if builder.Len() < maxDigits {
				builder.WriteByte(d)
			}
			continue
		}

		if separatorWordSet[folded] {
			if started {
				continue
			}
			skippedBefore++
			if skippedBefore > 6 {
				break
			}
			continue
		}

		if started {
			break
		}

		skippedBefore++
		if skippedBefore > 6 {
			break
		}
	}

	return builder.String(), usedWords
}

func allASCIIDigits(value string) bool {
	if value == "" {
		return false
	}
	for _, r := range value {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

func labeledWordCandidates(text string, label *regexp.Regexp, maxDigits int) []string {
	matches := label.FindAllStringIndex(text, 32)
	out := []string{}

	for _, match := range matches {
		after := []rune(text[match[1]:])
		if len(after) > 220 {
			after = after[:220]
		}
		digitsValue, usedWords := parseDigitWords(string(after), maxDigits)
		if usedWords && digitsValue != "" {
			out = append(out, digitsValue)
		}
	}

	return out
}

func detectEvasiveIdentifiers(text string) []Detection {
	out := []Detection{}
	seen := map[string]bool{}
	runes := []rune(text)

	for _, run := range collectNumericRuns(text) {
		value := run.Digits

		if len(value) == 11 && validCPF(value) && (run.Obfuscated || run.Evasive) {
			addUniqueDetection(&out, seen, "CPF", value, runEvidence("cpf_checksum", run))
		}
		if len(value) == 14 && validCNPJ(value) && (run.Obfuscated || run.Evasive) {
			addUniqueDetection(&out, seen, "CNPJ", value, runEvidence("cnpj_checksum", run))
		}
		if len(value) >= 13 && len(value) <= 19 && validLuhn(value) && (run.Obfuscated || run.Evasive) {
			addUniqueDetection(&out, seen, "CREDIT_CARD", value, runEvidence("luhn_checksum", run))
		}

		if nearbyLabel(runes, run.Start, "cpf") {
			foundEmbedded := false
			if len(value) > 11 && len(value) <= 19 {
				if embedded, ok := validCPFWindow(value); ok {
					evidence := runEvidence("cpf_checksum+embedded_identifier+obfuscated_identifier", run)
					addUniqueDetection(&out, seen, "CPF", embedded, evidence)
					foundEmbedded = true
				}
			}

			if !foundEmbedded && (len(value) == 10 || len(value) == 12 || (len(value) == 11 && !validCPF(value))) {
				evidence := runEvidence("cpf_context+malformed_identifier", run)
				addUniqueDetection(&out, seen, "CPF_LIKE", value, evidence)
			}
		}
	}

	for _, value := range labeledWordCandidates(text, evasionCPFLabelRegex, 19) {
		if len(value) == 11 && validCPF(value) {
			addUniqueDetection(&out, seen, "CPF", value, "cpf_checksum+number_words+evasive_obfuscation")
			continue
		}
		if len(value) > 11 {
			if embedded, ok := validCPFWindow(value); ok {
				addUniqueDetection(&out, seen, "CPF", embedded, "cpf_checksum+number_words+embedded_identifier+evasive_obfuscation")
				continue
			}
		}
		if len(value) == 10 || len(value) == 12 || (len(value) == 11 && !validCPF(value)) {
			addUniqueDetection(&out, seen, "CPF_LIKE", value, "cpf_context+number_words+malformed_identifier+evasive_obfuscation")
		}
	}

	for _, value := range labeledWordCandidates(text, evasionCNPJLabelRegex, 18) {
		if len(value) == 14 && validCNPJ(value) {
			addUniqueDetection(&out, seen, "CNPJ", value, "cnpj_checksum+number_words+evasive_obfuscation")
		}
	}

	for _, value := range labeledWordCandidates(text, evasionCardLabelRegex, 19) {
		if len(value) >= 13 && len(value) <= 19 && validLuhn(value) {
			addUniqueDetection(&out, seen, "CREDIT_CARD", value, "luhn_checksum+number_words+evasive_obfuscation")
		}
	}

	return out
}
