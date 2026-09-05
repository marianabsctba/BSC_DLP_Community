package main

import "testing"

func TestBrowserExtensionRequestAllowed(t *testing.T) {
	cases := []struct {
		origin string
		marker string
		want   bool
	}{
		{"chrome-extension://abc123", "1", true},
		{"moz-extension://abc123", "1", true},
		{"", "1", true},
		{"https://web.whatsapp.com", "1", false},
		{"http://evil.example", "1", false},
		{"chrome-extension://abc123", "", false},
	}

	for _, tc := range cases {
		got := browserExtensionRequestAllowed(tc.origin, tc.marker)
		if got != tc.want {
			t.Fatalf("origin=%q marker=%q got=%v want=%v", tc.origin, tc.marker, got, tc.want)
		}
	}
}

func TestNormalizeBrowserDestination(t *testing.T) {
	if got := normalizeBrowserDestination("web.whatsapp.com"); got != "whatsapp_web" {
		t.Fatalf("unexpected destination: %s", got)
	}
	if got := normalizeBrowserDestination("WhatsApp"); got != "whatsapp_web" {
		t.Fatalf("unexpected destination: %s", got)
	}
}
