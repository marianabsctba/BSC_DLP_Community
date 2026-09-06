//go:build windows

package main

import (
	"os/exec"
	"strings"
)

func platformBrowserRunning(browser string) bool {
	exe := guardBrowserProcessName(browser)
	if exe == "" {
		return false
	}

	out, err := exec.Command(
		"tasklist.exe",
		"/FI", "IMAGENAME eq "+exe,
		"/FO", "CSV",
		"/NH",
	).CombinedOutput()
	if err != nil {
		return false
	}
	return strings.Contains(strings.ToLower(string(out)), strings.ToLower(exe))
}
