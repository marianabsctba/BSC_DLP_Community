package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
)

const version = "0.6.3"

var recentEvents = map[string]time.Time{}
var recentEventsMu sync.Mutex
var pendingInspections = map[string]bool{}
var pendingInspectionsMu sync.Mutex
var agentToken string
var customRulesMu sync.Mutex
var customRulesCache []CustomDetectionRule
var customRulesFetchedAt time.Time

var cpfRegex = regexp.MustCompile(`\d{3}[.,\s]?\d{3}[.,\s]?\d{3}[-\s]?\d{2}`)

type Heartbeat struct {
	EndpointID   string `json:"endpoint_id"`
	Hostname     string `json:"hostname"`
	OS           string `json:"os,omitempty"`
	AgentVersion string `json:"agent_version"`
	Username     string `json:"username,omitempty"`
}

type PolicyDecision struct {
	Matched        bool   `json:"matched"`
	Policy         string `json:"policy"`
	Classification string `json:"classification"`
	Severity       string `json:"severity"`
	Action         string `json:"action"`
	Channel        string `json:"channel"`
	Priority       int    `json:"priority"`
}

type Event struct {
	EventID             string   `json:"event_id"`
	EndpointID          string   `json:"endpoint_id"`
	Hostname            string   `json:"hostname"`
	Username            string   `json:"username,omitempty"`
	Process             string   `json:"process,omitempty"`
	ObjectPath          string   `json:"object_path,omitempty"`
	ObjectHash          string   `json:"object_hash,omitempty"`
	Classification      string   `json:"classification"`
	Severity            string   `json:"severity"`
	Action              string   `json:"action"`
	MaskedValue         string   `json:"masked_value,omitempty"`
	Fingerprint         string   `json:"fingerprint,omitempty"`
	Channel             string   `json:"channel"`
	Policy              string   `json:"policy,omitempty"`
	Evidence            string   `json:"evidence,omitempty"`
	Blocked             bool     `json:"blocked"`
	DocumentType        string   `json:"document_type,omitempty"`
	Destination         string   `json:"destination,omitempty"`
	DetectionCount      int      `json:"detection_count,omitempty"`
	ClassificationCount int      `json:"classification_count,omitempty"`
	ContextTags         []string `json:"context_tags,omitempty"`
	SensitiveFilename   bool     `json:"sensitive_filename,omitempty"`
	DestinationTrust    string   `json:"destination_trust,omitempty"`
}

func digits(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func validCPF(v string) bool {
	n := digits(v)

	if len(n) != 11 {
		return false
	}

	allSame := true
	for i := 1; i < len(n); i++ {
		if n[i] != n[0] {
			allSame = false
			break
		}
	}
	if allSame {
		return false
	}

	for size := 9; size <= 10; size++ {
		total := 0

		for i := 0; i < size; i++ {
			total += int(n[i]-'0') * (size + 1 - i)
		}

		d := (total * 10) % 11
		if d == 10 {
			d = 0
		}

		if d != int(n[size]-'0') {
			return false
		}
	}

	return true
}

func fingerprint(v string) string {
	sum := sha256.Sum256([]byte(v))
	return hex.EncodeToString(sum[:])
}

func mask(v string) string {
	if len(v) <= 4 {
		return strings.Repeat("*", len(v))
	}
	return strings.Repeat("*", len(v)-4) + v[len(v)-4:]
}

func loadAgentToken() string {
	tokenFile := strings.TrimSpace(os.Getenv("BSC_DLP_TOKEN_FILE"))

	if tokenFile != "" {
		data, err := os.ReadFile(tokenFile)
		if err != nil {
			log.Printf("cannot read agent token file: %v", err)
			return ""
		}

		return strings.TrimSpace(string(data))
	}

	return strings.TrimSpace(os.Getenv("BSC_DLP_TOKEN"))
}

func postJSON(url string, body any) error {
	data, err := json.Marshal(body)
	if err != nil {
		return err
	}

	req, err := http.NewRequest(
		http.MethodPost,
		url,
		bytes.NewReader(data),
	)
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")

	if agentToken != "" {
		req.Header.Set(
			"Authorization",
			"Bearer "+agentToken,
		)
	}

	client := http.Client{
		Timeout: 5 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	io.Copy(io.Discard, resp.Body)

	if resp.StatusCode >= 300 {
		return fmt.Errorf("HTTP %s", resp.Status)
	}

	return nil
}

func resolvePolicy(api, classification, channel string) PolicyDecision {
	fallback := PolicyDecision{
		Matched:        false,
		Policy:         "Default Audit",
		Classification: classification,
		Severity:       "MEDIUM",
		Action:         "AUDIT",
		Channel:        channel,
		Priority:       9999,
	}

	endpoint := fmt.Sprintf(
		"%s/policies/resolve?classification=%s&channel=%s",
		api,
		classification,
		channel,
	)

	req, err := http.NewRequest(
		http.MethodGet,
		endpoint,
		nil,
	)
	if err != nil {
		log.Printf("policy request error: %v; using fallback", err)
		return fallback
	}

	if agentToken != "" {
		req.Header.Set(
			"Authorization",
			"Bearer "+agentToken,
		)
	}

	client := http.Client{
		Timeout: 3 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		log.Printf("policy resolve error: %v; using fallback", err)
		return fallback
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		log.Printf(
			"policy resolve HTTP %s; using fallback",
			resp.Status,
		)
		return fallback
	}

	var decision PolicyDecision

	if err := json.NewDecoder(resp.Body).Decode(&decision); err != nil {
		log.Printf("policy decode error: %v; using fallback", err)
		return fallback
	}

	switch strings.ToUpper(decision.Action) {
	case "AUDIT", "ALERT", "BLOCK", "QUARANTINE", "ALLOW":
	default:
		log.Printf("policy requested unknown action=%s; falling back to ALERT", decision.Action)
		decision.Action = "ALERT"
	}

	return decision
}

func customDetectionRules(api string) []CustomDetectionRule {
	customRulesMu.Lock()
	defer customRulesMu.Unlock()

	if time.Since(customRulesFetchedAt) < 60*time.Second {
		return append([]CustomDetectionRule(nil), customRulesCache...)
	}
	customRulesFetchedAt = time.Now()
	if agentToken == "" {
		return append([]CustomDetectionRule(nil), customRulesCache...)
	}

	req, err := http.NewRequest(http.MethodGet, api+"/agent/detection-rules", nil)
	if err != nil {
		return append([]CustomDetectionRule(nil), customRulesCache...)
	}
	req.Header.Set("Authorization", "Bearer "+agentToken)
	client := http.Client{Timeout: 3 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("custom detector refresh error: %v", err)
		return append([]CustomDetectionRule(nil), customRulesCache...)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		log.Printf("custom detector refresh HTTP %s", resp.Status)
		return append([]CustomDetectionRule(nil), customRulesCache...)
	}
	var rules []CustomDetectionRule
	if err := json.NewDecoder(resp.Body).Decode(&rules); err != nil {
		log.Printf("custom detector decode error: %v", err)
		return append([]CustomDetectionRule(nil), customRulesCache...)
	}
	customRulesCache = rules
	return append([]CustomDetectionRule(nil), customRulesCache...)
}

func extractOCR(path string) (string, error) {
	ext := strings.ToLower(filepath.Ext(path))

	switch ext {
	case ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp":
	default:
		return "", fmt.Errorf("unsupported image type: %s", ext)
	}

	tesseract := commandPath("BSC_DLP_TESSERACT", "tesseract")
	if tesseract == "" {
		return "", fmt.Errorf("OCR engine unavailable: tesseract was not found")
	}

	languages := []string{}
	if raw := strings.TrimSpace(os.Getenv("BSC_DLP_OCR_LANGS")); raw != "" {
		for _, value := range strings.FieldsFunc(raw, func(r rune) bool { return r == ',' || r == ';' }) {
			value = strings.TrimSpace(value)
			if value != "" {
				languages = append(languages, value)
			}
		}
	}
	if len(languages) == 0 {
		languages = []string{"por+eng", "eng"}
	}

	var lastErr error
	for _, language := range languages {
		cmd := exec.Command(
			tesseract,
			path,
			"stdout",
			"-l",
			language,
			"--psm",
			"6",
		)
		output, err := cmd.CombinedOutput()
		if err == nil && strings.TrimSpace(string(output)) != "" {
			return string(output), nil
		}
		if err != nil {
			lastErr = fmt.Errorf("tesseract language=%s failed: %v: %s", language, err, strings.TrimSpace(string(output)))
		}
	}

	if lastErr == nil {
		lastErr = fmt.Errorf("tesseract produced no OCR text")
	}
	return "", lastErr
}

func fileHash(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}

	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func inspect(path, api, endpointID, hostname, username, channel string) {
	info, err := os.Stat(path)
	if err != nil || info.IsDir() {
		return
	}

	if info.Size() > maxInspectionBytes() {
		log.Printf("inspection skipped: file too large path=%s size=%d", path, info.Size())
		return
	}

	text, inspection, docType, err := extractTextFromPath(path, channel)
	if err != nil {
		// Unsupported extensions are intentionally silent to avoid noisy endpoint logs.
		if !strings.Contains(err.Error(), "unsupported document type") {
			log.Printf("inspection error path=%s error=%v", path, err)
		}
		return
	}

	detections := detectSensitiveWithRules(text, customDetectionRules(api))
	if len(detections) == 0 {
		return
	}

	objectContext := buildObjectContext(path, channel, detections)
	objectHash := fileHash(path)
	blockedByClassification := map[string]bool{}
	enforcementEvidence := map[string]string{}
	policyByClassification := map[string]PolicyDecision{}

	// Resolve all policies before mutating/quarantining the source object.
	for _, detection := range detections {
		if _, exists := policyByClassification[detection.Classification]; !exists {
			policyByClassification[detection.Classification] = resolvePolicy(api, detection.Classification, channel)
		}
	}

	// A single BLOCK decision on the object enforces once, then every related event
	// records the actual outcome. This avoids trying to quarantine the same file twice.
	for classification, decision := range policyByClassification {
		action := strings.ToUpper(decision.Action)
		if action != "BLOCK" && action != "QUARANTINE" {
			continue
		}
		blocked, evidence := enforcePath(path, action)
		blockedByClassification[classification] = blocked
		enforcementEvidence[classification] = evidence
		if blocked {
			log.Printf("endpoint enforcement: action=%s path=%s result=quarantined", action, path)
		} else {
			log.Printf("endpoint enforcement failed: action=%s path=%s detail=%s", action, path, evidence)
		}
		// After the first successful quarantine the path no longer exists; one object
		// mutation is enough even when several classifiers matched.
		if blocked {
			for other := range policyByClassification {
				if other != classification {
					blockedByClassification[other] = true
					enforcementEvidence[other] = "endpoint_quarantine"
				}
			}
			break
		}
	}

	for _, detection := range detections {
		fp := fingerprint(detection.Value)
		dedupKey := path + "|" + detection.Classification + "|" + fp
		recentEventsMu.Lock()
		last, exists := recentEvents[dedupKey]
		if exists && time.Since(last) < 3*time.Second {
			recentEventsMu.Unlock()
			continue
		}
		recentEvents[dedupKey] = time.Now()
		recentEventsMu.Unlock()

		decision := policyByClassification[detection.Classification]
		evidence := inspection + "+" + detection.Evidence
		if len(objectContext.ContextTags) > 0 {
			evidence += "+context:" + strings.Join(objectContext.ContextTags, ",")
		}
		if extra := enforcementEvidence[detection.Classification]; extra != "" {
			evidence += "+" + extra
		}

		event := Event{
			EventID: fmt.Sprintf(
				"%s-%d",
				fingerprint(path + detection.Classification + detection.Value)[:12],
				time.Now().UnixNano(),
			),
			EndpointID:          endpointID,
			Hostname:            hostname,
			Username:            username,
			Process:             "bsc-dlp-agent",
			ObjectPath:          path,
			ObjectHash:          objectHash,
			Classification:      detection.Classification,
			Severity:            decision.Severity,
			Action:              decision.Action,
			MaskedValue:         mask(detection.Value),
			Fingerprint:         fp,
			Channel:             channel,
			Policy:              decision.Policy,
			Evidence:            evidence,
			Blocked:             blockedByClassification[detection.Classification],
			DocumentType:        docType,
			DetectionCount:      objectContext.DetectionCount,
			ClassificationCount: objectContext.ClassificationCount,
			ContextTags:         objectContext.ContextTags,
			SensitiveFilename:   objectContext.SensitiveFilename,
			DestinationTrust:    objectContext.DestinationTrust,
		}

		if err := postJSON(api+"/events", event); err != nil {
			log.Printf("event error: %v", err)
			continue
		}

		log.Printf(
			"DLP event: classification=%s path=%s channel=%s action=%s blocked=%t policy=%s",
			detection.Classification,
			path,
			channel,
			decision.Action,
			event.Blocked,
			decision.Policy,
		)
	}
}

func waitForStableFile(path string, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	var lastSize int64 = -1
	var lastMod time.Time
	stableSamples := 0

	for time.Now().Before(deadline) {
		info, err := os.Stat(path)
		if err == nil && !info.IsDir() {
			if info.Size() == lastSize && info.ModTime().Equal(lastMod) {
				stableSamples++
			} else {
				lastSize = info.Size()
				lastMod = info.ModTime()
				stableSamples = 0
			}
			if stableSamples >= 2 {
				return true
			}
		}
		time.Sleep(250 * time.Millisecond)
	}
	return false
}

func scheduleInspection(path, api, endpointID, hostname, username, channel string) {
	path = filepath.Clean(path)
	if !supportedDocumentPath(path) {
		return
	}

	pendingInspectionsMu.Lock()
	if pendingInspections[path] {
		pendingInspectionsMu.Unlock()
		return
	}
	pendingInspections[path] = true
	pendingInspectionsMu.Unlock()

	go func() {
		defer func() {
			pendingInspectionsMu.Lock()
			delete(pendingInspections, path)
			pendingInspectionsMu.Unlock()
		}()

		if !waitForStableFile(path, 5*time.Second) {
			log.Printf("inspection deferred: file did not settle path=%s", path)
			return
		}
		inspect(path, api, endpointID, hostname, username, channel)
	}()
}

func scanRecentDirectory(dir string, since time.Time, watchRoots map[string]string, api, endpointID, hostname, username string) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		path := filepath.Join(dir, entry.Name())
		if !supportedDocumentPath(path) {
			continue
		}
		info, err := entry.Info()
		if err != nil || info.ModTime().Before(since) {
			continue
		}
		channel := channelForPath(path, watchRoots)
		scheduleInspection(path, api, endpointID, hostname, username, channel)
	}
}

func addRecursiveWatches(watcher *fsnotify.Watcher, root string) error {
	return filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			log.Printf("recursive watch walk error path=%s error=%v", path, err)
			return nil
		}

		if !info.IsDir() {
			return nil
		}

		if err := watcher.Add(path); err != nil {
			log.Printf("recursive watch add error path=%s error=%v", path, err)
		}

		return nil
	})
}

func parseWatchRoots(raw string) map[string]string {
	roots := map[string]string{}

	for _, item := range strings.Split(raw, ",") {
		parts := strings.SplitN(strings.TrimSpace(item), "=", 2)

		if len(parts) != 2 {
			continue
		}

		root := filepath.Clean(strings.TrimSpace(parts[0]))
		channel := strings.ToLower(strings.TrimSpace(parts[1]))

		if root == "" || channel == "" {
			continue
		}

		roots[root] = channel
	}

	return roots
}

func channelForPath(path string, watchRoots map[string]string) string {
	channel := "filesystem"
	bestRootLen := -1

	for root, configuredChannel := range watchRoots {
		rel, err := filepath.Rel(root, path)

		if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			continue
		}

		if len(root) > bestRootLen {
			bestRootLen = len(root)
			channel = configuredChannel
		}
	}

	return channel
}

func syncDefaultWatches(watcher *fsnotify.Watcher, watchRoots map[string]string) {
	for root, channel := range defaultWatchRoots() {
		root = filepath.Clean(root)

		if _, exists := watchRoots[root]; exists {
			continue
		}

		if _, err := os.Stat(root); err != nil {
			continue
		}

		if err := addRecursiveWatches(watcher, root); err != nil {
			log.Printf("default watch error root=%s channel=%s error=%v", root, channel, err)
			continue
		}

		watchRoots[root] = channel
		log.Printf("default watch discovered root=%s channel=%s", root, channel)
	}
}

func syncRemovableWatches(
	watcher *fsnotify.Watcher,
	watchRoots map[string]string,
	dynamicRemovable map[string]bool,
) {
	current := platformRemovableRoots()

	for root := range dynamicRemovable {
		if _, mounted := current[root]; mounted {
			continue
		}

		_ = watcher.Remove(root)
		delete(dynamicRemovable, root)
		delete(watchRoots, root)
		log.Printf("removable media removed root=%s", root)
	}

	for root, channel := range current {
		root = filepath.Clean(root)

		if dynamicRemovable[root] {
			continue
		}

		if _, err := os.Stat(root); err != nil {
			continue
		}

		if err := addRecursiveWatches(watcher, root); err != nil {
			log.Printf("removable watch error root=%s error=%v", root, err)
			continue
		}

		watchRoots[root] = channel
		dynamicRemovable[root] = true
		log.Printf("removable media detected root=%s channel=%s", root, channel)
	}
}

type EnrollRequest struct {
	EndpointID string `json:"endpoint_id"`
}

type EnrollResponse struct {
	Status     string `json:"status"`
	EndpointID string `json:"endpoint_id"`
	Token      string `json:"token"`
}

func writeAgentToken(path, token string) error {
	if path == "" {
		return fmt.Errorf("BSC_DLP_TOKEN_FILE is required for automatic enrollment")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(token), 0600)
}

func enrollAgent(api, endpointID string) (string, error) {
	enrollmentKey := strings.TrimSpace(os.Getenv("BSC_DLP_ENROLLMENT_KEY"))
	if enrollmentKey == "" {
		return "", fmt.Errorf("enrollment key not configured")
	}

	data, err := json.Marshal(EnrollRequest{EndpointID: endpointID})
	if err != nil {
		return "", err
	}
	req, err := http.NewRequest(http.MethodPost, api+"/enroll", bytes.NewReader(data))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Enrollment-Key", enrollmentKey)

	resp, err := (&http.Client{Timeout: 8 * time.Second}).Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return "", fmt.Errorf("enrollment HTTP %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	var result EnrollResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}
	if strings.TrimSpace(result.Token) == "" {
		return "", fmt.Errorf("enrollment response did not include a token")
	}
	return strings.TrimSpace(result.Token), nil
}

func configureLogging() func() {
	logFile := strings.TrimSpace(os.Getenv("BSC_DLP_LOG_FILE"))
	if logFile == "" {
		return func() {}
	}

	if err := os.MkdirAll(filepath.Dir(logFile), 0700); err != nil {
		log.Printf("cannot create log directory: %v", err)
		return func() {}
	}

	f, err := os.OpenFile(logFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		log.Printf("cannot open log file: %v", err)
		return func() {}
	}

	log.SetOutput(io.MultiWriter(os.Stderr, f))
	return func() { _ = f.Close() }
}

func main() {
	closeLog := configureLogging()
	defer closeLog()

	api := strings.TrimSpace(os.Getenv("BSC_DLP_API"))
	if api == "" {
		api = "http://127.0.0.1:8000/api/v1"
	}

	agentToken = loadAgentToken()

	if agentToken == "" {
		log.Printf("agent authentication: token not configured")
	} else {
		log.Printf("agent authentication: bearer token loaded")
	}

	watchesEnv := strings.TrimSpace(os.Getenv("BSC_DLP_WATCHES"))
	explicitWatches := watchesEnv != ""

	var watchRoots map[string]string
	if explicitWatches {
		watchRoots = parseWatchRoots(watchesEnv)
	} else {
		watchRoots = defaultWatchRoots()
	}

	hostname, _ := os.Hostname()
	endpointID := strings.TrimSpace(os.Getenv("BSC_DLP_ENDPOINT_ID"))
	if endpointID == "" {
		endpointID = "bsc-dlp-" + hostname
	}

	if agentToken == "" && strings.TrimSpace(os.Getenv("BSC_DLP_ENROLLMENT_KEY")) != "" {
		token, err := enrollAgent(api, endpointID)
		if err != nil {
			log.Printf("automatic enrollment failed: %v", err)
		} else {
			tokenFile := strings.TrimSpace(os.Getenv("BSC_DLP_TOKEN_FILE"))
			if err := writeAgentToken(tokenFile, token); err != nil {
				log.Printf("could not persist enrolled token: %v", err)
			} else {
				agentToken = token
				log.Printf("automatic enrollment completed endpoint=%s", endpointID)
			}
		}
	}

	u, _ := user.Current()
	username := ""
	if u != nil {
		username = u.Username
	}

	for root := range watchRoots {
		if _, err := os.Stat(root); err == nil {
			continue
		}

		if explicitWatches || shouldCreateWatchRoot(root) {
			if err := os.MkdirAll(root, 0755); err != nil {
				log.Printf("cannot create watch root %s: %v", root, err)
				delete(watchRoots, root)
			}
			continue
		}

		log.Printf("watch root unavailable; skipping root=%s", root)
		delete(watchRoots, root)
	}

	hb := Heartbeat{
		EndpointID:   endpointID,
		Hostname:     hostname,
		OS:           platformOSName(),
		AgentVersion: version,
		Username:     username,
	}

	if err := postJSON(api+"/endpoints/heartbeat", hb); err != nil {
		log.Printf("heartbeat error: %v", err)
	} else {
		log.Printf("heartbeat sent endpoint=%s", endpointID)
	}

	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()

		for range ticker.C {
			if err := postJSON(api+"/endpoints/heartbeat", hb); err != nil {
				log.Printf("heartbeat error: %v", err)
			}
		}
	}()

	startMessagingClipboardSensor(api, endpointID, hostname, username)
	startBrowserBridge(api, endpointID, hostname, username)

	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		log.Fatal(err)
	}
	defer watcher.Close()

	for root, channel := range watchRoots {
		if err := addRecursiveWatches(watcher, root); err != nil {
			log.Printf("watch error root=%s channel=%s error=%v", root, channel, err)
			continue
		}

		log.Printf(
			"BSC DLP Agent v%s os=%s watching %s recursively channel=%s",
			version,
			platformOSName(),
			root,
			channel,
		)
	}

	dynamicRemovable := map[string]bool{}
	syncRemovableWatches(watcher, watchRoots, dynamicRemovable)

	removableTicker := time.NewTicker(10 * time.Second)
	defer removableTicker.Stop()

	for {
		select {
		case event := <-watcher.Events:
			if event.Op&(fsnotify.Create|fsnotify.Write|fsnotify.Rename) != 0 {
				if info, err := os.Stat(event.Name); err == nil && info.IsDir() {
					if event.Op&(fsnotify.Create|fsnotify.Rename) != 0 {
						if err := addRecursiveWatches(watcher, event.Name); err != nil {
							log.Printf(
								"dynamic recursive watch error path=%s error=%v",
								event.Name,
								err,
							)
						} else {
							log.Printf(
								"dynamic recursive watch added path=%s",
								event.Name,
							)
						}
					}
					continue
				}

				if abs, err := filepath.Abs(event.Name); err == nil {
					channel := channelForPath(abs, watchRoots)
					scheduleInspection(abs, api, endpointID, hostname, username, channel)

					// Browsers commonly download to .crdownload/.tmp and then rename.
					// Some fsnotify backends report only the old name. Rescan the parent
					// briefly after a rename so the final PNG/JPG/PDF is not missed.
					if event.Op&fsnotify.Rename != 0 {
						parent := filepath.Dir(abs)
						go func() {
							time.Sleep(600 * time.Millisecond)
							scanRecentDirectory(
								parent,
								time.Now().Add(-10*time.Second),
								watchRoots,
								api,
								endpointID,
								hostname,
								username,
							)
						}()
					}
				}
			}

		case <-removableTicker.C:
			if !explicitWatches {
				syncDefaultWatches(watcher, watchRoots)
			}
			syncRemovableWatches(watcher, watchRoots, dynamicRemovable)

		case err := <-watcher.Errors:
			log.Printf("watcher error: %v", err)
		}
	}
}
