package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

const browserBridgeDefaultAddr = "127.0.0.1:8765"

type BrowserInspectRequest struct {
	Destination string `json:"destination"`
	PageURL     string `json:"page_url"`
	EventType   string `json:"event_type"`
	Browser     string `json:"browser"`
	Text        string `json:"text"`
}

type BrowserInspectResponse struct {
	Status          string   `json:"status"`
	Block           bool     `json:"block"`
	Action          string   `json:"action"`
	Classifications []string `json:"classifications"`
	Reason          string   `json:"reason,omitempty"`
}

func browserBridgeAddr() string {
	value := strings.TrimSpace(os.Getenv("BSC_DLP_BROWSER_BRIDGE"))
	if value == "" {
		return browserBridgeDefaultAddr
	}
	return value
}

func browserExtensionRequestAllowed(origin, marker string) bool {
	if strings.TrimSpace(marker) != "1" {
		return false
	}
	origin = strings.ToLower(strings.TrimSpace(origin))
	if origin == "" {
		return true
	}
	return strings.HasPrefix(origin, "chrome-extension://") ||
		strings.HasPrefix(origin, "moz-extension://")
}

func normalizeBrowserDestination(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	switch value {
	case "whatsapp", "whatsapp_web", "web.whatsapp.com":
		return "whatsapp_web"
	case "teams", "teams_web":
		return "teams_web"
	case "slack", "slack_web":
		return "slack_web"
	case "telegram", "telegram_web":
		return "telegram_web"
	default:
		return value
	}
}

func browserBridgeEnabled() bool {
	raw := strings.ToLower(strings.TrimSpace(os.Getenv("BSC_DLP_BROWSER_SENSOR")))
	return raw != "0" && raw != "false" && raw != "off" && raw != "disabled"
}

func startBrowserBridge(api, endpointID, hostname, username string) {
	if !browserBridgeEnabled() {
		log.Printf("browser messaging bridge disabled by BSC_DLP_BROWSER_SENSOR")
		return
	}

	addr := browserBridgeAddr()
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		log.Printf("browser messaging bridge unavailable addr=%s error=%v", addr, err)
		return
	}

	mux := http.NewServeMux()

	mux.HandleFunc("/v1/health", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok","service":"bsc-dlp-browser-bridge","version":"0.6.2"}`))
	})

	mux.HandleFunc("/v1/inspect", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !browserExtensionRequestAllowed(
			r.Header.Get("Origin"),
			r.Header.Get("X-BSC-DLP-Extension"),
		) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}

		r.Body = http.MaxBytesReader(w, r.Body, 1024*1024)
		defer r.Body.Close()

		var body BrowserInspectRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}

		body.Text = strings.TrimSpace(body.Text)
		body.Destination = normalizeBrowserDestination(body.Destination)
		body.EventType = strings.ToLower(strings.TrimSpace(body.EventType))

		if body.Text == "" {
			writeBrowserJSON(w, BrowserInspectResponse{Status: "ok", Action: "ALLOW"})
			return
		}
		if body.Destination == "" {
			http.Error(w, "destination is required", http.StatusBadRequest)
			return
		}

		detections := detectSensitiveWithRules(body.Text, customDetectionRules(api))
		if len(detections) == 0 {
			writeBrowserJSON(w, BrowserInspectResponse{Status: "ok", Action: "ALLOW"})
			return
		}

		objectContext := buildObjectContext("browser-composer.txt", "messaging", detections)
		objectContext.DestinationTrust = "external"

		classSet := map[string]bool{}
		classes := make([]string, 0, len(detections))
		decisions := map[string]PolicyDecision{}
		overallAction := "AUDIT"
		shouldBlock := false

		for _, detection := range detections {
			if !classSet[detection.Classification] {
				classSet[detection.Classification] = true
				classes = append(classes, detection.Classification)
			}
			if _, exists := decisions[detection.Classification]; exists {
				continue
			}
			decision := resolvePolicy(api, detection.Classification, "messaging")
			decisions[detection.Classification] = decision

			switch strings.ToUpper(decision.Action) {
			case "BLOCK", "QUARANTINE":
				overallAction = decision.Action
				shouldBlock = true
			case "ALERT":
				if !shouldBlock {
					overallAction = "ALERT"
				}
			}
		}

		for _, detection := range detections {
			decision := decisions[detection.Classification]
			blocked := shouldBlock && shouldMessagingClipboardBlock(decision.Action)

			evidence := "browser_outgoing_text+" + body.Destination
			if body.EventType != "" {
				evidence += "+" + body.EventType
			}

			processName := strings.TrimSpace(body.Browser)
			if processName == "" {
				processName = "browser-extension"
			}

			event := Event{
				EventID: fmt.Sprintf(
					"%s-%d",
					fingerprint("browser|" + body.Destination + "|" + detection.Classification + "|" + detection.Value)[:12],
					time.Now().UnixNano(),
				),
				EndpointID:          endpointID,
				Hostname:            hostname,
				Username:            username,
				Process:             processName,
				ObjectPath:          "browser://" + body.Destination + "/composer",
				ObjectHash:          fingerprint(body.Text),
				Classification:      detection.Classification,
				Severity:            decision.Severity,
				Action:              decision.Action,
				MaskedValue:         mask(detection.Value),
				Fingerprint:         fingerprint(detection.Value),
				Channel:             "messaging",
				Destination:         body.Destination,
				Policy:              decision.Policy,
				Evidence:            evidence,
				Blocked:             blocked,
				DocumentType:        "browser_text",
				DetectionCount:      objectContext.DetectionCount,
				ClassificationCount: objectContext.ClassificationCount,
				ContextTags:         objectContext.ContextTags,
				SensitiveFilename:   false,
				DestinationTrust:    "external",
			}

			if err := postJSON(api+"/events", event); err != nil {
				log.Printf("browser messaging event error: %v", err)
			}
		}

		writeBrowserJSON(w, BrowserInspectResponse{
			Status:          "ok",
			Block:           shouldBlock,
			Action:          overallAction,
			Classifications: classes,
		})
	})

	server := &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 3 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	go func() {
		log.Printf("browser messaging bridge active http://%s", addr)
		if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
			log.Printf("browser messaging bridge error: %v", err)
		}
	}()
}

func writeBrowserJSON(w http.ResponseWriter, payload BrowserInspectResponse) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(payload)
}
