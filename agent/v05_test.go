package main

import "testing"

func TestExpandedSensitiveDetectors(t *testing.T) {
	text := `
Email: maria.teste@example.com
RG: 12.345.678-9
CEP: 80000-000
Telefone: (41) 99999-0000
Chave PIX: pix-chave-12345
Agência: 1234, Conta: 123456-7
Passaporte: AB123456
senha=SuperSecret123!
api_key=abcdefgh12345678
Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456
`
	got := detectSensitive(text)
	want := map[string]bool{
		"EMAIL_ADDRESS": false,
		"RG_BR":         false,
		"CEP_BR":        false,
		"PHONE_BR":      false,
		"PIX_KEY":       false,
		"BANK_ACCOUNT":  false,
		"PASSPORT":      false,
		"CREDENTIAL":    false,
		"SECRET":        false,
	}
	for _, d := range got {
		if _, ok := want[d.Classification]; ok {
			want[d.Classification] = true
		}
	}
	for class, found := range want {
		if !found {
			t.Fatalf("missing classification %s in %#v", class, got)
		}
	}
}

func TestCustomDetectionRule(t *testing.T) {
	rules := []CustomDetectionRule{{
		ID: 1, Name: "Contrato", Classification: "CONTRACT_ID", Pattern: `CONTRATO-[0-9]{8}`, Enabled: true,
	}}
	got := detectSensitiveWithRules("Documento CONTRATO-20260905 aprovado", rules)
	for _, d := range got {
		if d.Classification == "CONTRACT_ID" && d.Value == "CONTRATO-20260905" {
			return
		}
	}
	t.Fatalf("custom detection missing: %#v", got)
}
