package main

import (
	"path/filepath"
	"testing"
)

func TestValidCPF(t *testing.T) {
	tests := []struct {
		value string
		want  bool
	}{
		{"529.982.247-25", true},
		{"52998224725", true},
		{"111.111.111-11", false},
		{"529.982.247-24", false},
	}

	for _, tt := range tests {
		if got := validCPF(tt.value); got != tt.want {
			t.Fatalf("validCPF(%q)=%v want %v", tt.value, got, tt.want)
		}
	}
}

func TestChannelForPathPrefersMostSpecificRoot(t *testing.T) {
	pictures := filepath.Join("tmp", "user", "Pictures")
	screenshots := filepath.Join(pictures, "Screenshots")
	file := filepath.Join(screenshots, "capture.png")

	roots := map[string]string{
		pictures:    "filesystem",
		screenshots: "screenshot",
	}

	if got := channelForPath(file, roots); got != "screenshot" {
		t.Fatalf("channelForPath()=%q want screenshot", got)
	}
}

func TestParseWatchRoots(t *testing.T) {
	rootA := filepath.Clean(filepath.Join("tmp", "Downloads"))
	rootB := filepath.Clean(filepath.Join("tmp", "Screenshots"))
	raw := rootA + "=download," + rootB + "=screenshot"

	got := parseWatchRoots(raw)

	if got[rootA] != "download" {
		t.Fatalf("download channel missing: %#v", got)
	}
	if got[rootB] != "screenshot" {
		t.Fatalf("screenshot channel missing: %#v", got)
	}
}
