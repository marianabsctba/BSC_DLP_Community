package main

import (
    "fmt"
    "log"
    "strings"
    "sync"
    "time"
)

const (
    browserGuardHeartbeatTimeout = 150 * time.Second
    browserGuardStartupGrace     = 120 * time.Second
    browserGuardCheckInterval    = 30 * time.Second
)

type BrowserGuardHeartbeatRequest struct {
    Browser          string `json:"browser"`
    ExtensionVersion string `json:"extension_version"`
    InstallID        string `json:"install_id"`
}

type browserGuardPresence struct {
    LastSeen         time.Time
    ExtensionVersion string
    InstallID        string
    RunningSince     time.Time
    AlertedMissing   bool
}

var (
    browserGuardPresenceMu        sync.Mutex
    browserGuardPresenceByBrowser = map[string]*browserGuardPresence{}
)

func normalizeGuardBrowser(value string) string {
    value = strings.ToLower(strings.TrimSpace(value))
    switch {
    case value == "edge", value == "msedge", strings.Contains(value, "edg/"):
        return "edge"
    case value == "firefox", strings.Contains(value, "firefox/"):
        return "firefox"
    case value == "chrome", value == "chromium", strings.Contains(value, "chrome/"):
        return "chrome"
    default:
        return ""
    }
}

func guardBrowserProcessName(browser string) string {
    switch normalizeGuardBrowser(browser) {
    case "edge":
        return "msedge.exe"
    case "firefox":
        return "firefox.exe"
    case "chrome":
        return "chrome.exe"
    default:
        return browser
    }
}

func recordBrowserGuardHeartbeat(api, endpointID, hostname, username string, body BrowserGuardHeartbeatRequest) error {
    browser := normalizeGuardBrowser(body.Browser)
    if browser == "" {
        return fmt.Errorf("unsupported browser")
    }

    now := time.Now()
    browserGuardPresenceMu.Lock()
    state := browserGuardPresenceByBrowser[browser]
    if state == nil {
        state = &browserGuardPresence{}
        browserGuardPresenceByBrowser[browser] = state
    }
    restored := state.AlertedMissing
    state.LastSeen = now
    state.ExtensionVersion = strings.TrimSpace(body.ExtensionVersion)
    state.InstallID = strings.TrimSpace(body.InstallID)
    state.AlertedMissing = false
    extensionVersion := state.ExtensionVersion
    browserGuardPresenceMu.Unlock()

    if restored {
        emitBrowserGuardPresenceEvent(
            api, endpointID, hostname, username, browser,
            "BROWSER_GUARD_RESTORED", "LOW", "AUDIT",
            "browser_guard_heartbeat_restored",
        )
        log.Printf("browser guard restored browser=%s version=%s", browser, extensionVersion)
    }
    return nil
}

func startBrowserGuardPresenceWatch(api, endpointID, hostname, username string) {
    go func() {
        ticker := time.NewTicker(browserGuardCheckInterval)
        defer ticker.Stop()

        time.Sleep(10 * time.Second)
        checkBrowserGuardPresence(api, endpointID, hostname, username)

        for range ticker.C {
            checkBrowserGuardPresence(api, endpointID, hostname, username)
        }
    }()
}

func checkBrowserGuardPresence(api, endpointID, hostname, username string) {
    now := time.Now()
    for _, browser := range []string{"chrome", "edge", "firefox"} {
        running := platformBrowserRunning(browser)

        browserGuardPresenceMu.Lock()
        state := browserGuardPresenceByBrowser[browser]
        if state == nil {
            state = &browserGuardPresence{}
            browserGuardPresenceByBrowser[browser] = state
        }

        if !running {
            state.RunningSince = time.Time{}
            browserGuardPresenceMu.Unlock()
            continue
        }

        if state.RunningSince.IsZero() {
            state.RunningSince = now
        }

        heartbeatFresh := !state.LastSeen.IsZero() && now.Sub(state.LastSeen) <= browserGuardHeartbeatTimeout
        graceElapsed := now.Sub(state.RunningSince) >= browserGuardStartupGrace
        shouldAlert := !heartbeatFresh && graceElapsed && !state.AlertedMissing
        lastSeen := state.LastSeen
        version := state.ExtensionVersion
        if shouldAlert {
            state.AlertedMissing = true
        }
        browserGuardPresenceMu.Unlock()

        if !shouldAlert {
            continue
        }

        reason := "browser_running+extension_heartbeat_missing"
        if !lastSeen.IsZero() {
            reason += "+last_seen:" + lastSeen.UTC().Format(time.RFC3339)
        } else {
            reason += "+never_seen"
        }
        if version != "" {
            reason += "+last_version:" + version
        }

        emitBrowserGuardPresenceEvent(
            api, endpointID, hostname, username, browser,
            "BROWSER_GUARD_DISABLED_OR_MISSING", "HIGH", "ALERT", reason,
        )
        log.Printf("browser guard protection gap browser=%s process=%s", browser, guardBrowserProcessName(browser))
    }
}

func emitBrowserGuardPresenceEvent(
    api, endpointID, hostname, username, browser,
    classification, severity, action, evidence string,
) {
    now := time.Now()
    basis := fmt.Sprintf("browser-guard|%s|%s|%s|%d", endpointID, browser, classification, now.UnixNano())
    event := Event{
        EventID:             fingerprint(basis)[:24],
        EndpointID:          endpointID,
        Hostname:            hostname,
        Username:            username,
        Process:             guardBrowserProcessName(browser),
        ObjectPath:          "browser://" + browser + "/guard",
        Classification:      classification,
        Severity:            severity,
        Action:              action,
        Fingerprint:         fingerprint(endpointID + "|" + browser + "|browser_guard"),
        Channel:             "browser_guard",
        Destination:         browser,
        Policy:              "Browser Guard Presence Watch",
        Evidence:            evidence,
        Blocked:             false,
        DetectionCount:      1,
        ClassificationCount: 1,
        ContextTags:         []string{"browser_guard", strings.ToLower(classification)},
        DestinationTrust:    "local",
    }

    if err := postJSON(api+"/events", event); err != nil {
        log.Printf("browser guard presence event error browser=%s classification=%s error=%v", browser, classification, err)
    }
}
