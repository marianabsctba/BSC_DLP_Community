package main

import (
	"strings"
	"testing"
)

func findDetection(items []Detection, classification string) *Detection {
	for i := range items {
		if items[i].Classification == classification {
			return &items[i]
		}
	}
	return nil
}

func TestEvasionCPFHashSeparators(t *testing.T) {
	got := detectSensitive("CPF: 123 # 456 # 789 # 09")
	d := findDetection(got, "CPF")
	if d == nil {
		t.Fatalf("CPF obfuscated with hashes was not detected: %#v", got)
	}
	if !strings.Contains(d.Evidence, "obfuscated_identifier") {
		t.Fatalf("missing obfuscation evidence: %#v", d)
	}
}

func TestEvasionCPFNumberWordsPortuguese(t *testing.T) {
	got := detectSensitive("CPF assim: um dois tres quatro cinco seis sete oito nove zero nove")
	d := findDetection(got, "CPF")
	if d == nil {
		t.Fatalf("CPF written as number words was not detected: %#v", got)
	}
	if !strings.Contains(d.Evidence, "number_words") || !strings.Contains(d.Evidence, "evasive_obfuscation") {
		t.Fatalf("missing number-word evasion evidence: %#v", d)
	}
}

func TestEvasionCPFNumberWordsEnglishAndSpanish(t *testing.T) {
	english := detectSensitive("CPF: one two three four five six seven eight nine zero nine")
	if findDetection(english, "CPF") == nil {
		t.Fatalf("English number words were not detected: %#v", english)
	}

	spanish := detectSensitive("CPF: uno dos tres cuatro cinco seis siete ocho nueve cero nueve")
	if findDetection(spanish, "CPF") == nil {
		t.Fatalf("Spanish number words were not detected: %#v", spanish)
	}
}

func TestEvasionCPFZeroWidth(t *testing.T) {
	got := detectSensitive("CPF: 123\u200b456\u200b789\u200b09")
	d := findDetection(got, "CPF")
	if d == nil {
		t.Fatalf("CPF with zero-width separators was not detected: %#v", got)
	}
	if !strings.Contains(d.Evidence, "evasive_obfuscation") {
		t.Fatalf("missing evasive evidence: %#v", d)
	}
}

func TestEvasionMalformedCPFWithContext(t *testing.T) {
	got := detectSensitive("CPF: 123 # 456 # 789 # 0")
	d := findDetection(got, "CPF_LIKE")
	if d == nil {
		t.Fatalf("malformed CPF with explicit context was not surfaced: %#v", got)
	}
	if !strings.Contains(d.Evidence, "malformed_identifier") {
		t.Fatalf("missing malformed evidence: %#v", d)
	}
}

func TestEvasionCNPJAndCard(t *testing.T) {
	cnpj := detectSensitive("CNPJ: 11 # 222 # 333 # 0001 # 81")
	if findDetection(cnpj, "CNPJ") == nil {
		t.Fatalf("obfuscated CNPJ not detected: %#v", cnpj)
	}

	card := detectSensitive("Cartão: 4111 # 1111 # 1111 # 1111")
	if findDetection(card, "CREDIT_CARD") == nil {
		t.Fatalf("obfuscated card not detected: %#v", card)
	}
}

func TestEvasionDoesNotMergeUnrelatedNumbers(t *testing.T) {
	got := detectSensitive("Pedido 123\nCliente 456\nRamal 789\nAndar 09")
	if findDetection(got, "CPF") != nil || findDetection(got, "CPF_LIKE") != nil {
		t.Fatalf("unrelated numbers must not be merged into a CPF: %#v", got)
	}
}

func TestPhoneIsNotNative(t *testing.T) {
	for _, d := range detectSensitive("Telefone: (41) 99999-0000") {
		if d.Classification == "PHONE_BR" {
			t.Fatalf("phone must be optional/custom in v0.6.3: %#v", d)
		}
	}
}
