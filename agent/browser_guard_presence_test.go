package main

import "testing"

func TestNormalizeGuardBrowser(t *testing.T) {
	cases := map[string]string{
		"chrome": "chrome",
		"Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36":               "chrome",
		"Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0": "edge",
		"Mozilla/5.0 Firefox/142.0":                                "firefox",
		"unknown":                                                  "",
	}
	for input, want := range cases {
		if got := normalizeGuardBrowser(input); got != want {
			t.Fatalf("normalizeGuardBrowser(%q)=%q want=%q", input, got, want)
		}
	}
}

func TestGuardBrowserProcessName(t *testing.T) {
	if got := guardBrowserProcessName("edge"); got != "msedge.exe" {
		t.Fatalf("edge process=%q", got)
	}
	if got := guardBrowserProcessName("firefox"); got != "firefox.exe" {
		t.Fatalf("firefox process=%q", got)
	}
	if got := guardBrowserProcessName("chrome"); got != "chrome.exe" {
		t.Fatalf("chrome process=%q", got)
	}
}
