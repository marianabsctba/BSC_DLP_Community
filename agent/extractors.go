package main

import (
	"archive/zip"
	"bytes"
	"compress/zlib"
	"encoding/xml"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"unicode/utf8"
)

func maxInspectionBytes() int64 {
	return 25 * 1024 * 1024
}

func documentType(path string) string {
	ext := strings.TrimPrefix(strings.ToLower(filepath.Ext(path)), ".")
	if ext == "" {
		return "unknown"
	}
	return ext
}

func supportedDocumentPath(path string) bool {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp",
		".pdf", ".docx", ".xlsx", ".pptx",
		".txt", ".csv", ".json", ".xml", ".log", ".md", ".ini", ".conf", ".yaml", ".yml":
		return true
	default:
		return false
	}
}

func readTextFile(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	if int64(len(data)) > maxInspectionBytes() {
		return "", fmt.Errorf("file exceeds inspection limit")
	}
	if !utf8.Valid(data) {
		// Best effort: ASCII/ANSI data still has useful digits and markers.
		return string(bytes.ToValidUTF8(data, []byte(" "))), nil
	}
	return string(data), nil
}

func extractXMLText(r io.Reader) (string, error) {
	dec := xml.NewDecoder(r)
	var b strings.Builder
	for {
		tok, err := dec.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return b.String(), nil // retain best-effort text for imperfect office XML
		}
		if ch, ok := tok.(xml.CharData); ok {
			value := strings.TrimSpace(string(ch))
			if value != "" {
				b.WriteString(value)
				b.WriteByte(' ')
			}
		}
	}
	return b.String(), nil
}

func officeEntryRelevant(ext, name string) bool {
	name = strings.ToLower(name)
	switch ext {
	case ".docx":
		return strings.HasPrefix(name, "word/") && strings.HasSuffix(name, ".xml")
	case ".xlsx":
		return (strings.HasPrefix(name, "xl/worksheets/") || strings.HasSuffix(name, "sharedstrings.xml")) && strings.HasSuffix(name, ".xml")
	case ".pptx":
		return (strings.HasPrefix(name, "ppt/slides/") || strings.HasPrefix(name, "ppt/notesSlides/")) && strings.HasSuffix(name, ".xml")
	}
	return false
}

func extractOpenXML(path string) (string, error) {
	zr, err := zip.OpenReader(path)
	if err != nil {
		return "", err
	}
	defer zr.Close()

	ext := strings.ToLower(filepath.Ext(path))
	var b strings.Builder
	for _, f := range zr.File {
		if !officeEntryRelevant(ext, f.Name) {
			continue
		}
		rc, err := f.Open()
		if err != nil {
			continue
		}
		text, _ := extractXMLText(io.LimitReader(rc, maxInspectionBytes()))
		_ = rc.Close()
		if text != "" {
			b.WriteString(text)
			b.WriteByte('\n')
		}
		if int64(b.Len()) >= maxInspectionBytes() {
			break
		}
	}
	if strings.TrimSpace(b.String()) == "" {
		return "", fmt.Errorf("no extractable OpenXML text")
	}
	return b.String(), nil
}

func commandPath(envName, fallback string) string {
	if configured := strings.TrimSpace(os.Getenv(envName)); configured != "" {
		return configured
	}
	if p, err := exec.LookPath(fallback); err == nil {
		return p
	}
	return ""
}

func pdfLiteralStrings(data []byte) string {
	var out strings.Builder
	for i := 0; i < len(data); i++ {
		if data[i] != '(' {
			continue
		}
		i++
		var s strings.Builder
		escaped := false
		for ; i < len(data); i++ {
			c := data[i]
			if escaped {
				switch c {
				case 'n':
					s.WriteByte('\n')
				case 'r':
					s.WriteByte('\r')
				case 't':
					s.WriteByte('\t')
				case 'b':
					s.WriteByte('\b')
				case 'f':
					s.WriteByte('\f')
				default:
					s.WriteByte(c)
				}
				escaped = false
				continue
			}
			if c == '\\' {
				escaped = true
				continue
			}
			if c == ')' {
				break
			}
			if c >= 32 || c == '\n' || c == '\r' || c == '\t' {
				s.WriteByte(c)
			}
		}
		value := strings.TrimSpace(s.String())
		if len(value) >= 2 {
			out.WriteString(value)
			out.WriteByte(' ')
		}
	}
	return out.String()
}

func extractPDFBuiltin(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	if int64(len(data)) > maxInspectionBytes() {
		return "", fmt.Errorf("PDF exceeds inspection limit")
	}

	var b strings.Builder
	b.WriteString(pdfLiteralStrings(data))

	marker := []byte("stream")
	endMarker := []byte("endstream")
	pos := 0
	for {
		idx := bytes.Index(data[pos:], marker)
		if idx < 0 {
			break
		}
		start := pos + idx + len(marker)
		for start < len(data) && (data[start] == '\r' || data[start] == '\n' || data[start] == ' ') {
			start++
		}
		endRel := bytes.Index(data[start:], endMarker)
		if endRel < 0 {
			break
		}
		end := start + endRel
		raw := bytes.TrimRight(data[start:end], "\r\n ")
		if zr, err := zlib.NewReader(bytes.NewReader(raw)); err == nil {
			decoded, _ := io.ReadAll(io.LimitReader(zr, maxInspectionBytes()))
			_ = zr.Close()
			b.WriteString(pdfLiteralStrings(decoded))
			b.WriteByte(' ')
		}
		pos = end + len(endMarker)
		if pos >= len(data) {
			break
		}
	}
	text := strings.TrimSpace(b.String())
	if text == "" {
		return "", fmt.Errorf("no built-in PDF text extracted")
	}
	return text, nil
}

func extractPDFWithTools(path string) (string, string, error) {
	if pdftotext := commandPath("BSC_DLP_PDFTOTEXT", "pdftotext"); pdftotext != "" {
		cmd := exec.Command(pdftotext, "-enc", "UTF-8", path, "-")
		if output, err := cmd.Output(); err == nil && strings.TrimSpace(string(output)) != "" {
			return string(output), "pdf_text", nil
		}
	}

	if text, err := extractPDFBuiltin(path); err == nil && strings.TrimSpace(text) != "" {
		return text, "pdf_builtin", nil
	}

	pdftoppm := commandPath("BSC_DLP_PDFTOPPM", "pdftoppm")
	tesseract := commandPath("BSC_DLP_TESSERACT", "tesseract")
	if pdftoppm == "" || tesseract == "" {
		return "", "", fmt.Errorf("scanned PDF needs pdftoppm + tesseract")
	}

	dir, err := os.MkdirTemp("", "bsc-dlp-pdf-ocr-")
	if err != nil {
		return "", "", err
	}
	defer os.RemoveAll(dir)

	prefix := filepath.Join(dir, "page")
	cmd := exec.Command(pdftoppm, "-png", "-r", "160", "-f", "1", "-l", "20", path, prefix)
	if output, err := cmd.CombinedOutput(); err != nil {
		return "", "", fmt.Errorf("pdftoppm failed: %v %s", err, strings.TrimSpace(string(output)))
	}

	pages, _ := filepath.Glob(prefix + "-*.png")
	sort.Strings(pages)
	var b strings.Builder
	for _, page := range pages {
		ocr := exec.Command(tesseract, page, "stdout", "-l", "por+eng", "--psm", "6")
		output, err := ocr.Output()
		if err == nil {
			b.Write(output)
			b.WriteByte('\n')
		}
	}
	if strings.TrimSpace(b.String()) == "" {
		return "", "", fmt.Errorf("PDF OCR produced no text")
	}
	return b.String(), "pdf_ocr", nil
}

func extractTextFromPath(path, channel string) (string, string, string, error) {
	ext := strings.ToLower(filepath.Ext(path))
	docType := documentType(path)

	switch ext {
	case ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp":
		text, err := extractOCR(path)
		return text, "image_ocr", docType, err
	case ".pdf":
		text, evidence, err := extractPDFWithTools(path)
		return text, evidence, docType, err
	case ".docx", ".xlsx", ".pptx":
		text, err := extractOpenXML(path)
		return text, "openxml_text", docType, err
	case ".txt", ".csv", ".json", ".xml", ".log", ".md", ".ini", ".conf", ".yaml", ".yml":
		text, err := readTextFile(path)
		return text, "text_content", docType, err
	default:
		if channel == "screenshot" {
			text, err := extractOCR(path)
			return text, "screenshot_ocr", docType, err
		}
		return "", "", docType, fmt.Errorf("unsupported document type: %s", ext)
	}
}
