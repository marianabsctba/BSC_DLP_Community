package main

import (
	"strings"
	"testing"
)

func hasClass(detections []Detection, class string) bool {
	for _, d := range detections {
		if d.Classification == class {
			return true
		}
	}
	return false
}

func TestSensitiveCatalogCoversFrameworkFamilies(t *testing.T) {
	required := []string{
		"CPF", "RG_BR", "PASSPORT", "EMAIL_ADDRESS", "PHONE_BR", "DATE_OF_BIRTH",
		"PHYSICAL_ADDRESS", "IP_ADDRESS", "GEOLOCATION", "HEALTH_DATA",
		"BIOMETRIC_DATA", "GENETIC_DATA", "CREDIT_CARD", "CARD_SECURITY_CODE",
		"CARD_PIN", "CARD_TRACK_DATA", "SECRET", "CREDENTIAL",
	}
	for _, class := range required {
		if _, ok := sensitiveDataCatalog[class]; !ok {
			t.Fatalf("catalog missing %s", class)
		}
	}
}

func TestCPFDoesNotRequireLiteralCPFLabel(t *testing.T) {
	d := detectSensitiveWithRules("Documento: 123.456.789-09", nil)
	if !hasClass(d, "CPF") {
		t.Fatalf("expected CPF checksum detection without CPF label: %#v", d)
	}
}

func TestFormattedPhoneDetectedWithoutPhoneLabel(t *testing.T) {
	d := detectSensitiveWithRules("Contato de emergência: (41) 91234-5678", nil)
	if !hasClass(d, "PHONE_BR") {
		t.Fatalf("expected PHONE_BR: %#v", d)
	}
}

func TestBirthDateContext(t *testing.T) {
	d := detectSensitiveWithRules("Data de nascimento: 29/08/1989", nil)
	if !hasClass(d, "DATE_OF_BIRTH") {
		t.Fatalf("expected DATE_OF_BIRTH: %#v", d)
	}
}

func TestAddressPattern(t *testing.T) {
	d := detectSensitiveWithRules("Rua das Flores, 123 Curitiba", nil)
	if !hasClass(d, "PHYSICAL_ADDRESS") {
		t.Fatalf("expected PHYSICAL_ADDRESS: %#v", d)
	}
}

func TestPCIAuthenticationData(t *testing.T) {
	d := detectSensitiveWithRules("CVV: 123", nil)
	if !hasClass(d, "CARD_SECURITY_CODE") {
		t.Fatalf("expected CARD_SECURITY_CODE: %#v", d)
	}
}

func TestCNPJIsBusinessDataNotPII(t *testing.T) {
	entry := sensitiveDataCatalog["CNPJ"]
	if entry.Family != "business_data" {
		t.Fatalf("CNPJ family=%q", entry.Family)
	}
}

func TestCatalogAggregatePIIBundle(t *testing.T) {
	d := []Detection{
		{Classification: "EMAIL_ADDRESS", Value: "ana@example.test", Evidence: "email_pattern"},
		{Classification: "PHONE_BR", Value: "(41) 91234-5678", Evidence: "phone_br_formatted_pattern"},
		{Classification: "DATE_OF_BIRTH", Value: "29/08/1989", Evidence: "date_of_birth_context"},
	}
	tags := strings.Join(catalogAggregateTags(d), ",")
	if !strings.Contains(tags, "pii_bundle") || !strings.Contains(tags, "pii_profile") {
		t.Fatalf("aggregate tags=%s", tags)
	}
}

func TestSpecialCategoryPlusIdentityGetsHighRiskTag(t *testing.T) {
	d := []Detection{
		{Classification: "CPF", Value: "12345678909", Evidence: "cpf_checksum"},
		{Classification: "CNS_BR", Value: "123456789012345", Evidence: "cns_health_identifier_context"},
	}
	tags := strings.Join(catalogAggregateTags(d), ",")
	if !strings.Contains(tags, "special_category_linked_identity") {
		t.Fatalf("aggregate tags=%s", tags)
	}
}

func TestCEPremainsSupportingEvidenceNotNativeClass(t *testing.T) {
	if _, ok := sensitiveDataCatalog["CEP_BR"]; ok {
		t.Fatal("CEP_BR must not be a standalone native catalog classification")
	}
}
