package main

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

const (
	browserBridgeDefaultAddr = "127.0.0.1:8765"
	browserUploadChunkMax    = 512 * 1024
	browserUploadSessionTTL  = 5 * time.Minute
)

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

type BrowserUploadStartRequest struct {
	Destination string `json:"destination"`
	PageURL     string `json:"page_url"`
	EventType   string `json:"event_type"`
	Browser     string `json:"browser"`
	Filename    string `json:"filename"`
	ContentType string `json:"content_type"`
	Size        int64  `json:"size"`
}

type BrowserUploadChunkRequest struct {
	UploadID string `json:"upload_id"`
	Sequence int    `json:"sequence"`
	Data     string `json:"data"`
}

type BrowserUploadFinishRequest struct {
	UploadID string `json:"upload_id"`
}

type browserUploadSession struct {
	ID           string
	Path         string
	Destination  string
	PageURL      string
	EventType    string
	Browser      string
	Filename     string
	ContentType  string
	ExpectedSize int64
	Received     int64
	NextSequence int
	CreatedAt    time.Time
}

var (
	browserUploadSessions   = map[string]*browserUploadSession{}
	browserUploadSessionsMu sync.Mutex
)

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

func normalizeBrowserUploadDestination(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	value = strings.TrimPrefix(value, "https://")
	value = strings.TrimPrefix(value, "http://")
	if slash := strings.IndexByte(value, '/'); slash >= 0 {
		value = value[:slash]
	}
	return strings.TrimSpace(value)
}

func browserBridgeEnabled() bool {
	raw := strings.ToLower(strings.TrimSpace(os.Getenv("BSC_DLP_BROWSER_SENSOR")))
	return raw != "0" && raw != "false" && raw != "off" && raw != "disabled"
}

func newBrowserUploadID() (string, error) {
	raw := make([]byte, 18)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	return hex.EncodeToString(raw), nil
}

func removeBrowserUploadSession(uploadID string) *browserUploadSession {
	browserUploadSessionsMu.Lock()
	session := browserUploadSessions[uploadID]
	delete(browserUploadSessions, uploadID)
	browserUploadSessionsMu.Unlock()
	return session
}

func cleanupBrowserUploadSessions() {
	cutoff := time.Now().Add(-browserUploadSessionTTL)
	var stale []*browserUploadSession

	browserUploadSessionsMu.Lock()
	for id, session := range browserUploadSessions {
		if session.CreatedAt.Before(cutoff) {
			stale = append(stale, session)
			delete(browserUploadSessions, id)
		}
	}
	browserUploadSessionsMu.Unlock()

	for _, session := range stale {
		_ = os.Remove(session.Path)
	}
}

func startBrowserUploadSession(body BrowserUploadStartRequest) (*browserUploadSession, string, error) {
	body.Filename = filepath.Base(strings.TrimSpace(body.Filename))
	body.Destination = normalizeBrowserUploadDestination(body.Destination)
	body.EventType = strings.ToLower(strings.TrimSpace(body.EventType))

	if body.Filename == "" || body.Filename == "." {
		return nil, "", fmt.Errorf("filename is required")
	}
	if body.Destination == "" {
		return nil, "", fmt.Errorf("destination is required")
	}
	if body.Size < 0 {
		return nil, "", fmt.Errorf("invalid file size")
	}
	if body.Size > maxInspectionBytes() {
		return nil, "file_too_large", nil
	}
	if !supportedDocumentPath(body.Filename) {
		return nil, "unsupported_file_type", nil
	}

	uploadID, err := newBrowserUploadID()
	if err != nil {
		return nil, "", err
	}

	ext := strings.ToLower(filepath.Ext(body.Filename))
	temp, err := os.CreateTemp("", "bsc-dlp-browser-upload-*"+ext)
	if err != nil {
		return nil, "", err
	}
	tempPath := temp.Name()
	if err := temp.Close(); err != nil {
		_ = os.Remove(tempPath)
		return nil, "", err
	}

	session := &browserUploadSession{
		ID:           uploadID,
		Path:         tempPath,
		Destination:  body.Destination,
		PageURL:      strings.TrimSpace(body.PageURL),
		EventType:    body.EventType,
		Browser:      strings.TrimSpace(body.Browser),
		Filename:     body.Filename,
		ContentType:  strings.TrimSpace(body.ContentType),
		ExpectedSize: body.Size,
		CreatedAt:    time.Now(),
	}

	browserUploadSessionsMu.Lock()
	browserUploadSessions[uploadID] = session
	browserUploadSessionsMu.Unlock()

	return session, "", nil
}

func appendBrowserUploadChunk(body BrowserUploadChunkRequest) error {
	body.UploadID = strings.TrimSpace(body.UploadID)
	if body.UploadID == "" {
		return fmt.Errorf("upload_id is required")
	}
	if len(body.Data) > (browserUploadChunkMax*4/3)+16 {
		return fmt.Errorf("chunk is too large")
	}

	decoded, err := base64.StdEncoding.DecodeString(body.Data)
	if err != nil {
		return fmt.Errorf("invalid chunk encoding")
	}
	if len(decoded) > browserUploadChunkMax {
		return fmt.Errorf("chunk is too large")
	}

	browserUploadSessionsMu.Lock()
	defer browserUploadSessionsMu.Unlock()

	session := browserUploadSessions[body.UploadID]
	if session == nil {
		return fmt.Errorf("upload session not found")
	}
	if body.Sequence != session.NextSequence {
		return fmt.Errorf("unexpected chunk sequence")
	}
	if session.Received+int64(len(decoded)) > maxInspectionBytes() {
		return fmt.Errorf("upload exceeds inspection limit")
	}
	if session.ExpectedSize > 0 && session.Received+int64(len(decoded)) > session.ExpectedSize {
		return fmt.Errorf("upload exceeds declared size")
	}

	f, err := os.OpenFile(session.Path, os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return err
	}
	_, writeErr := f.Write(decoded)
	closeErr := f.Close()
	if writeErr != nil {
		return writeErr
	}
	if closeErr != nil {
		return closeErr
	}

	session.Received += int64(len(decoded))
	session.NextSequence++
	return nil
}

func browserDecision(
	api, endpointID, hostname, username string,
	destination, browser, eventType, objectName, objectHash, inspection, docType, channel string,
	detections []Detection,
) BrowserInspectResponse {
	if len(detections) == 0 {
		return BrowserInspectResponse{
			Status: "ok",
			Action: "ALLOW",
			Reason: "no_sensitive_match",
		}
	}

	objectContext := buildObjectContext(objectName, channel, detections)
	if channel == "browser_upload" {
		objectContext.DestinationTrust = "external"
	}

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

		decision := resolvePolicy(api, detection.Classification, channel)
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

	processName := strings.TrimSpace(browser)
	if processName == "" {
		processName = "browser-extension"
	}
	if len(processName) > 240 {
		processName = processName[:240]
	}

	for _, detection := range detections {
		decision := decisions[detection.Classification]
		blocked := shouldBlock && shouldMessagingClipboardBlock(decision.Action)

		evidence := inspection + "+" + detection.Evidence
		if destination != "" {
			evidence += "+destination:" + destination
		}
		if eventType != "" {
			evidence += "+event:" + eventType
		}
		if len(objectContext.ContextTags) > 0 {
			evidence += "+context:" + strings.Join(objectContext.ContextTags, ",")
		}
		if blocked {
			evidence += "+browser_pre_upload_block"
		}

		objectPath := "browser://" + destination
		if channel == "browser_upload" {
			objectPath += "/upload/" + filepath.Base(objectName)
		} else {
			objectPath += "/composer"
		}

		event := Event{
			EventID: fmt.Sprintf(
				"%s-%d",
				fingerprint("browser|" + destination + "|" + objectName + "|" + detection.Classification + "|" + detection.Value)[:12],
				time.Now().UnixNano(),
			),
			EndpointID:          endpointID,
			Hostname:            hostname,
			Username:            username,
			Process:             processName,
			ObjectPath:          objectPath,
			ObjectHash:          objectHash,
			Classification:      detection.Classification,
			Severity:            decision.Severity,
			Action:              decision.Action,
			MaskedValue:         mask(detection.Value),
			Fingerprint:         fingerprint(detection.Value),
			Channel:             channel,
			Destination:         destination,
			Policy:              decision.Policy,
			Evidence:            evidence,
			Blocked:             blocked,
			DocumentType:        docType,
			DetectionCount:      objectContext.DetectionCount,
			ClassificationCount: objectContext.ClassificationCount,
			ContextTags:         objectContext.ContextTags,
			SensitiveFilename:   objectContext.SensitiveFilename,
			DestinationTrust:    objectContext.DestinationTrust,
		}

		if err := postJSON(api+"/events", event); err != nil {
			log.Printf("browser DLP event error: %v", err)
		}
	}

	return BrowserInspectResponse{
		Status:          "ok",
		Block:           shouldBlock,
		Action:          overallAction,
		Classifications: classes,
		Reason:          "sensitive_content",
	}
}

func finishBrowserUpload(
	api, endpointID, hostname, username string,
	uploadID string,
) BrowserInspectResponse {
	session := removeBrowserUploadSession(strings.TrimSpace(uploadID))
	if session == nil {
		return BrowserInspectResponse{
			Status: "error",
			Action: "ALLOW",
			Reason: "upload_session_not_found",
		}
	}
	defer os.Remove(session.Path)

	if session.ExpectedSize != session.Received {
		log.Printf(
			"browser upload size mismatch file=%s expected=%d received=%d",
			session.Filename,
			session.ExpectedSize,
			session.Received,
		)
		return BrowserInspectResponse{
			Status: "error",
			Action: "ALLOW",
			Reason: "upload_size_mismatch",
		}
	}

	text, inspection, docType, err := extractTextFromPath(session.Path, "browser_upload")
	if err != nil {
		log.Printf(
			"browser upload inspection error destination=%s file=%s error=%v",
			session.Destination,
			session.Filename,
			err,
		)
		return BrowserInspectResponse{
			Status: "ok",
			Action: "ALLOW",
			Reason: "inspection_error_fail_open",
		}
	}

	detections := detectSensitiveWithRules(text, customDetectionRules(api))
	return browserDecision(
		api,
		endpointID,
		hostname,
		username,
		session.Destination,
		session.Browser,
		session.EventType,
		session.Filename,
		fileHash(session.Path),
		"browser_file_upload+"+inspection,
		docType,
		"browser_upload",
		detections,
	)
}

func requireBrowserExtension(w http.ResponseWriter, r *http.Request) bool {
	if browserExtensionRequestAllowed(
		r.Header.Get("Origin"),
		r.Header.Get("X-BSC-DLP-Extension"),
	) {
		return true
	}
	http.Error(w, "forbidden", http.StatusForbidden)
	return false
}

func startBrowserBridge(api, endpointID, hostname, username string) {
	if !browserBridgeEnabled() {
		log.Printf("browser bridge disabled by BSC_DLP_BROWSER_SENSOR")
		return
	}

	addr := browserBridgeAddr()
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		log.Printf("browser bridge unavailable addr=%s error=%v", addr, err)
		return
	}

	mux := http.NewServeMux()

	mux.HandleFunc("/v1/health", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok","service":"bsc-dlp-browser-bridge","version":"0.6.6.3","file_upload":true,"guard_presence":true}`))
	})

	mux.HandleFunc("/v1/guard/heartbeat", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !requireBrowserExtension(w, r) {
			return
		}

		r.Body = http.MaxBytesReader(w, r.Body, 32*1024)
		defer r.Body.Close()

		var body BrowserGuardHeartbeatRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}
		if err := recordBrowserGuardHeartbeat(api, endpointID, hostname, username, body); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		writeBrowserJSON(w, map[string]any{
			"status":                    "ok",
			"browser":                   normalizeGuardBrowser(body.Browser),
			"heartbeat_timeout_seconds": int(browserGuardHeartbeatTimeout / time.Second),
		})
	})

	mux.HandleFunc("/v1/inspect", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !requireBrowserExtension(w, r) {
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
		response := browserDecision(
			api,
			endpointID,
			hostname,
			username,
			body.Destination,
			body.Browser,
			body.EventType,
			"browser-composer.txt",
			fingerprint(body.Text),
			"browser_outgoing_text",
			"browser_text",
			"messaging",
			detections,
		)
		writeBrowserJSON(w, response)
	})

	mux.HandleFunc("/v1/upload/start", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !requireBrowserExtension(w, r) {
			return
		}

		r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
		defer r.Body.Close()

		var body BrowserUploadStartRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}

		session, skipReason, err := startBrowserUploadSession(body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if skipReason != "" {
			writeBrowserJSON(w, map[string]any{
				"status":    "ok",
				"skip":      true,
				"action":    "ALLOW",
				"reason":    skipReason,
				"max_bytes": maxInspectionBytes(),
			})
			return
		}

		writeBrowserJSON(w, map[string]any{
			"status":    "ok",
			"upload_id": session.ID,
			"max_bytes": maxInspectionBytes(),
		})
	})

	mux.HandleFunc("/v1/upload/chunk", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !requireBrowserExtension(w, r) {
			return
		}

		r.Body = http.MaxBytesReader(w, r.Body, 1024*1024)
		defer r.Body.Close()

		var body BrowserUploadChunkRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}
		if err := appendBrowserUploadChunk(body); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		writeBrowserJSON(w, map[string]any{
			"status":   "ok",
			"sequence": body.Sequence,
		})
	})

	mux.HandleFunc("/v1/upload/finish", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !requireBrowserExtension(w, r) {
			return
		}

		r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
		defer r.Body.Close()

		var body BrowserUploadFinishRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}

		writeBrowserJSON(w, finishBrowserUpload(
			api,
			endpointID,
			hostname,
			username,
			body.UploadID,
		))
	})

	mux.HandleFunc("/v1/upload/cancel", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if !requireBrowserExtension(w, r) {
			return
		}

		r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
		defer r.Body.Close()

		var body BrowserUploadFinishRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "invalid json", http.StatusBadRequest)
			return
		}

		if session := removeBrowserUploadSession(strings.TrimSpace(body.UploadID)); session != nil {
			_ = os.Remove(session.Path)
		}
		writeBrowserJSON(w, map[string]any{"status": "ok"})
	})

	startBrowserGuardPresenceWatch(api, endpointID, hostname, username)

	server := &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 3 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	go func() {
		ticker := time.NewTicker(time.Minute)
		defer ticker.Stop()
		for range ticker.C {
			cleanupBrowserUploadSessions()
		}
	}()

	go func() {
		log.Printf("browser DLP bridge active http://%s (text + generic file upload + guard presence watch)", addr)
		if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
			log.Printf("browser DLP bridge error: %v", err)
		}
	}()
}

func writeBrowserJSON(w http.ResponseWriter, payload any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(payload)
}
