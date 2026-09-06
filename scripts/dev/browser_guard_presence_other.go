//go:build !windows

package main

import (
    "os"
    "path/filepath"
    "strconv"
    "strings"
)

func platformBrowserRunning(browser string) bool {
    candidates := map[string][]string{
        "chrome":  {"chrome", "google-chrome", "chromium", "chromium-browser"},
        "edge":    {"msedge", "microsoft-edge"},
        "firefox": {"firefox"},
    }[normalizeGuardBrowser(browser)]
    if len(candidates) == 0 {
        return false
    }

    entries, err := os.ReadDir("/proc")
    if err != nil {
        return false
    }
    for _, entry := range entries {
        if !entry.IsDir() {
            continue
        }
        if _, err := strconv.Atoi(entry.Name()); err != nil {
            continue
        }
        base := filepath.Join("/proc", entry.Name())
        comm, _ := os.ReadFile(filepath.Join(base, "comm"))
        cmdline, _ := os.ReadFile(filepath.Join(base, "cmdline"))
        haystack := strings.ToLower(string(comm) + " " + strings.ReplaceAll(string(cmdline), "\x00", " "))
        for _, candidate := range candidates {
            if strings.Contains(haystack, strings.ToLower(candidate)) {
                return true
            }
        }
    }
    return false
}
