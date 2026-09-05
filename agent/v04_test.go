package main

import (
	"archive/zip"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestMain(m *testing.M) {
	if os.Getenv("BSC_DLP_FAKE_TESSERACT") == "1" {
		args := strings.Join(os.Args[1:], " ")
		if strings.Contains(args, "por+eng") {
			_, _ = os.Stderr.WriteString("missing por language\\n")
			os.Exit(1)
		}
		_, _ = os.Stdout.WriteString("CPF 529.982.247-25\\n")
		os.Exit(0)
	}
	os.Exit(m.Run())
}

func TestDetectCNPJAndCard(t *testing.T) {
	text := "CNPJ 04.252.011/0001-10 cartão 4111 1111 1111 1111"
	detections := detectSensitive(text)
	got := map[string]bool{}
	for _, d := range detections {
		got[d.Classification] = true
	}
	if !got["CNPJ"] {
		t.Fatalf("expected CNPJ detection: %#v", detections)
	}
	if !got["CREDIT_CARD"] {
		t.Fatalf("expected CREDIT_CARD detection: %#v", detections)
	}
}

func TestOpenXMLExtraction(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sample.docx")
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	zw := zip.NewWriter(f)
	w, err := zw.Create("word/document.xml")
	if err != nil {
		t.Fatal(err)
	}
	_, _ = w.Write([]byte(`<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>CPF 529.982.247-25</w:t></w:r></w:p></w:body></w:document>`))
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}

	text, err := extractOpenXML(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "529.982.247-25") {
		t.Fatalf("missing extracted content: %q", text)
	}
}

func TestBuiltinPDFExtraction(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sample.pdf")
	pdf := "%PDF-1.4\n1 0 obj<<>>endobj\nBT (CPF 529.982.247-25) Tj ET\n%%EOF"
	if err := os.WriteFile(path, []byte(pdf), 0600); err != nil {
		t.Fatal(err)
	}
	text, err := extractPDFBuiltin(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "529.982.247-25") {
		t.Fatalf("missing PDF text: %q", text)
	}
}

func TestEndpointQuarantine(t *testing.T) {
	dir := t.TempDir()
	quarantine := filepath.Join(dir, "q")
	t.Setenv("BSC_DLP_QUARANTINE", quarantine)
	src := filepath.Join(dir, "sensitive.txt")
	if err := os.WriteFile(src, []byte("CPF 529.982.247-25"), 0600); err != nil {
		t.Fatal(err)
	}
	blocked, evidence := enforcePath(src, "BLOCK")
	if !blocked || evidence != "endpoint_quarantine" {
		t.Fatalf("enforcement failed blocked=%v evidence=%q", blocked, evidence)
	}
	if _, err := os.Stat(src); !os.IsNotExist(err) {
		t.Fatalf("source should be removed, stat err=%v", err)
	}
	entries, err := os.ReadDir(quarantine)
	if err != nil || len(entries) != 1 {
		t.Fatalf("quarantine content invalid entries=%d err=%v", len(entries), err)
	}
}

func TestInspectBlockEndToEnd(t *testing.T) {
	dir := t.TempDir()
	quarantine := filepath.Join(dir, "quarantine")
	t.Setenv("BSC_DLP_QUARANTINE", quarantine)

	var got Event
	mux := http.NewServeMux()
	mux.HandleFunc("/policies/resolve", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"matched":true,"policy":"CPF USB Block","classification":"CPF","severity":"CRITICAL","action":"BLOCK","channel":"removable","priority":1}`))
	})
	mux.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("decode event: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"accepted"}`))
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	oldToken := agentToken
	agentToken = "unit-test-token"
	defer func() { agentToken = oldToken }()

	src := filepath.Join(dir, "clientes.txt")
	if err := os.WriteFile(src, []byte("CPF 529.982.247-25"), 0600); err != nil {
		t.Fatal(err)
	}
	inspect(src, srv.URL, "ep-1", "WIN-TEST", "tester", "removable")

	if _, err := os.Stat(src); !os.IsNotExist(err) {
		t.Fatalf("blocked source should be removed, stat err=%v", err)
	}
	if !got.Blocked || got.Action != "BLOCK" || got.DocumentType != "txt" {
		t.Fatalf("unexpected event: %#v", got)
	}
	if !strings.Contains(got.Evidence, "endpoint_quarantine") {
		t.Fatalf("missing enforcement evidence: %q", got.Evidence)
	}
}

func TestDownloadImageUsesOCRWithLanguageFallback(t *testing.T) {
	dir := t.TempDir()
	img := filepath.Join(dir, "cpf-download.png")
	if err := os.WriteFile(img, []byte("not-a-real-image-the-fake-ocr-command-ignores-it"), 0600); err != nil {
		t.Fatal(err)
	}

	fake, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("BSC_DLP_FAKE_TESSERACT", "1")
	t.Setenv("BSC_DLP_TESSERACT", fake)
	t.Setenv("BSC_DLP_OCR_LANGS", "por+eng,eng")

	text, evidence, docType, err := extractTextFromPath(img, "download")
	if err != nil {
		t.Fatal(err)
	}
	if evidence != "image_ocr" || docType != "png" {
		t.Fatalf("unexpected extraction metadata evidence=%q docType=%q", evidence, docType)
	}
	detections := detectSensitive(text)
	if len(detections) == 0 || detections[0].Classification != "CPF" {
		t.Fatalf("expected CPF from image OCR fallback, text=%q detections=%#v", text, detections)
	}
}

func TestRecentDirectoryScanCatchesDownloadedImage(t *testing.T) {
	dir := t.TempDir()
	img := filepath.Join(dir, "browser-final.png")
	if err := os.WriteFile(img, []byte("fake-image"), 0600); err != nil {
		t.Fatal(err)
	}

	fake, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("BSC_DLP_FAKE_TESSERACT", "1")
	t.Setenv("BSC_DLP_TESSERACT", fake)
	t.Setenv("BSC_DLP_OCR_LANGS", "eng")

	events := make(chan Event, 1)
	mux := http.NewServeMux()
	mux.HandleFunc("/policies/resolve", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"matched":true,"policy":"CPF Download Alert","classification":"CPF","severity":"HIGH","action":"ALERT","channel":"download","priority":1}`))
	})
	mux.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		var got Event
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("decode event: %v", err)
		}
		select {
		case events <- got:
		default:
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"accepted"}`))
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	oldToken := agentToken
	agentToken = "unit-test-token"
	defer func() { agentToken = oldToken }()

	pendingInspectionsMu.Lock()
	pendingInspections = map[string]bool{}
	pendingInspectionsMu.Unlock()
	recentEventsMu.Lock()
	recentEvents = map[string]time.Time{}
	recentEventsMu.Unlock()

	scanRecentDirectory(
		dir,
		time.Now().Add(-10*time.Second),
		map[string]string{dir: "download"},
		srv.URL,
		"ep-browser",
		"WIN-BROWSER",
		"tester",
	)

	select {
	case got := <-events:
		if got.Channel != "download" || got.Classification != "CPF" || got.DocumentType != "png" {
			t.Fatalf("unexpected browser download event: %#v", got)
		}
		if !strings.Contains(got.Evidence, "image_ocr") {
			t.Fatalf("missing image OCR evidence: %q", got.Evidence)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("timed out waiting for downloaded image OCR event")
	}
}
