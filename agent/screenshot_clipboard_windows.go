//go:build windows

package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"log"
	"os"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	cfBitmap                = 2
	cfDIB                   = 8
	cfDIBV5                 = 17
	dibRGBColors            = 0
	maxClipboardImageBytes  = 64 * 1024 * 1024
	screenshotClipboardPoll = 650 * time.Millisecond
)

type winBitmap struct {
	Type       int32
	Width      int32
	Height     int32
	WidthBytes int32
	Planes     uint16
	BitsPixel  uint16
	Bits       uintptr
}

type bitmapInfoHeader struct {
	Size          uint32
	Width         int32
	Height        int32
	Planes        uint16
	BitCount      uint16
	Compression   uint32
	SizeImage     uint32
	XPelsPerMeter int32
	YPelsPerMeter int32
	ClrUsed       uint32
	ClrImportant  uint32
}

var (
	screenshotUser32 = syscall.NewLazyDLL("user32.dll")
	screenshotGDI32  = syscall.NewLazyDLL("gdi32.dll")

	procScreenshotGetDC      = screenshotUser32.NewProc("GetDC")
	procScreenshotReleaseDC  = screenshotUser32.NewProc("ReleaseDC")
	procScreenshotGetObjectW = screenshotGDI32.NewProc("GetObjectW")
	procScreenshotGetDIBits  = screenshotGDI32.NewProc("GetDIBits")
)

func screenshotClipboardSensorEnabled() bool {
	raw := strings.TrimSpace(strings.ToLower(os.Getenv("BSC_DLP_SCREENSHOT_CLIPBOARD_SENSOR")))
	return raw != "0" && raw != "false" && raw != "off" && raw != "disabled"
}

func absInt32(v int32) int32 {
	if v < 0 {
		return -v
	}
	return v
}

func hBitmapToBMP(hBitmap uintptr) ([]byte, error) {
	if hBitmap == 0 {
		return nil, fmt.Errorf("clipboard HBITMAP is null")
	}

	var bm winBitmap
	got, _, callErr := procScreenshotGetObjectW.Call(
		hBitmap,
		unsafe.Sizeof(bm),
		uintptr(unsafe.Pointer(&bm)),
	)
	if got == 0 || bm.Width <= 0 || bm.Height == 0 {
		return nil, fmt.Errorf(
			"GetObjectW failed width=%d height=%d error=%v",
			bm.Width,
			bm.Height,
			callErr,
		)
	}

	width := bm.Width
	height := absInt32(bm.Height)

	// Always ask GDI for a plain 24-bit BI_RGB bitmap. This intentionally
	// normalizes DIBV5/alpha/bitfield clipboard images into a format that
	// Leptonica/Tesseract reads reliably.
	stride := ((int(width)*24 + 31) / 32) * 4
	pixelBytes := stride * int(height)
	if pixelBytes <= 0 || pixelBytes > maxClipboardImageBytes {
		return nil, fmt.Errorf("clipboard bitmap exceeds OCR limit: %d bytes", pixelBytes)
	}

	header := bitmapInfoHeader{
		Size:        40,
		Width:       width,
		Height:      height,
		Planes:      1,
		BitCount:    24,
		Compression: biRGB,
		SizeImage:   uint32(pixelBytes),
	}

	hdc, _, dcErr := procScreenshotGetDC.Call(0)
	if hdc == 0 {
		return nil, fmt.Errorf("GetDC failed: %v", dcErr)
	}
	defer procScreenshotReleaseDC.Call(0, hdc)

	pixels := make([]byte, pixelBytes)
	lines, _, dibErr := procScreenshotGetDIBits.Call(
		hdc,
		hBitmap,
		0,
		uintptr(height),
		uintptr(unsafe.Pointer(&pixels[0])),
		uintptr(unsafe.Pointer(&header)),
		dibRGBColors,
	)
	if lines == 0 {
		return nil, fmt.Errorf("GetDIBits failed: %v", dibErr)
	}

	const fileHeaderSize = 14
	const infoHeaderSize = 40
	pixelOffset := fileHeaderSize + infoHeaderSize
	fileSize := pixelOffset + len(pixels)

	bmp := make([]byte, fileSize)
	bmp[0] = 'B'
	bmp[1] = 'M'
	binary.LittleEndian.PutUint32(bmp[2:6], uint32(fileSize))
	binary.LittleEndian.PutUint32(bmp[10:14], uint32(pixelOffset))

	binary.LittleEndian.PutUint32(bmp[14:18], header.Size)
	binary.LittleEndian.PutUint32(bmp[18:22], uint32(header.Width))
	binary.LittleEndian.PutUint32(bmp[22:26], uint32(header.Height))
	binary.LittleEndian.PutUint16(bmp[26:28], header.Planes)
	binary.LittleEndian.PutUint16(bmp[28:30], header.BitCount)
	binary.LittleEndian.PutUint32(bmp[30:34], header.Compression)
	binary.LittleEndian.PutUint32(bmp[34:38], header.SizeImage)
	binary.LittleEndian.PutUint32(bmp[38:42], uint32(header.XPelsPerMeter))
	binary.LittleEndian.PutUint32(bmp[42:46], uint32(header.YPelsPerMeter))
	binary.LittleEndian.PutUint32(bmp[46:50], header.ClrUsed)
	binary.LittleEndian.PutUint32(bmp[50:54], header.ClrImportant)

	copy(bmp[pixelOffset:], pixels)
	return bmp, nil
}

func readClipboardImageBMP() ([]byte, uint32, string, bool) {
	seq, _, _ := procMsgGetClipboardSequenceNumber.Call()

	// Prefer CF_BITMAP. Windows/GDI then converts any DIBV5/bitfield clipboard
	// representation into a standard uncompressed 24-bit BI_RGB BMP.
	available, _, _ := procMsgIsClipboardFormatAvailable.Call(cfBitmap)
	if available != 0 {
		opened, _, _ := procMsgOpenClipboard.Call(0)
		if opened == 0 {
			return nil, uint32(seq), "CF_BITMAP", false
		}
		defer procMsgCloseClipboard.Call()

		hBitmap, _, _ := procMsgGetClipboardData.Call(cfBitmap)
		if hBitmap == 0 {
			return nil, uint32(seq), "CF_BITMAP", false
		}

		bmp, err := hBitmapToBMP(hBitmap)
		if err != nil {
			log.Printf("clipboard CF_BITMAP conversion error: %v", err)
			return nil, uint32(seq), "CF_BITMAP", false
		}
		return bmp, uint32(seq), "CF_BITMAP", true
	}

	// Fallback only for uncompressed DIBs. Compressed/bitfield DIBs were the
	// v0.6.4 failure mode, so do not feed them directly to Tesseract.
	format := uintptr(cfDIBV5)
	available, _, _ = procMsgIsClipboardFormatAvailable.Call(format)
	if available == 0 {
		format = cfDIB
		available, _, _ = procMsgIsClipboardFormatAvailable.Call(format)
		if available == 0 {
			return nil, uint32(seq), "", false
		}
	}

	opened, _, _ := procMsgOpenClipboard.Call(0)
	if opened == 0 {
		return nil, uint32(seq), fmt.Sprintf("CF_%d", format), false
	}
	defer procMsgCloseClipboard.Call()

	handle, _, _ := procMsgGetClipboardData.Call(format)
	if handle == 0 {
		return nil, uint32(seq), fmt.Sprintf("CF_%d", format), false
	}

	sizeBytes, _, _ := procMsgGlobalSize.Call(handle)
	if sizeBytes < 40 || sizeBytes > maxClipboardImageBytes {
		return nil, uint32(seq), fmt.Sprintf("CF_%d", format), false
	}

	ptr, _, _ := procMsgGlobalLock.Call(handle)
	if ptr == 0 {
		return nil, uint32(seq), fmt.Sprintf("CF_%d", format), false
	}
	defer procMsgGlobalUnlock.Call(handle)

	raw := unsafe.Slice((*byte)(unsafe.Pointer(ptr)), int(sizeBytes))
	dib := append([]byte(nil), raw...)

	headerSize := int(binary.LittleEndian.Uint32(dib[0:4]))
	if headerSize >= 40 {
		compression := binary.LittleEndian.Uint32(dib[16:20])
		if compression != biRGB {
			log.Printf(
				"clipboard DIB fallback skipped: format=%d compression=%d requires CF_BITMAP normalization",
				format,
				compression,
			)
			return nil, uint32(seq), fmt.Sprintf("CF_%d", format), false
		}
	}

	bmp, err := dibToBMP(dib)
	if err != nil {
		log.Printf("clipboard DIB conversion error: %v", err)
		return nil, uint32(seq), fmt.Sprintf("CF_%d", format), false
	}
	return bmp, uint32(seq), fmt.Sprintf("CF_%d", format), true
}

func hashClipboardImage(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func ocrClipboardBMP(bmp []byte) (string, error) {
	f, err := os.CreateTemp("", "bsc-dlp-clipboard-screenshot-*.bmp")
	if err != nil {
		return "", err
	}
	path := f.Name()
	defer os.Remove(path)

	if _, err := f.Write(bmp); err != nil {
		_ = f.Close()
		return "", err
	}
	if err := f.Close(); err != nil {
		return "", err
	}

	return extractOCR(path)
}

func startScreenshotClipboardSensor(api, endpointID, hostname, username string) {
	if !screenshotClipboardSensorEnabled() {
		log.Printf("screenshot clipboard sensor disabled by BSC_DLP_SCREENSHOT_CLIPBOARD_SENSOR")
		return
	}

	go func() {
		ticker := time.NewTicker(screenshotClipboardPoll)
		defer ticker.Stop()

		var lastSequence uint32
		log.Printf("screenshot clipboard OCR sensor active (Windows; CF_BITMAP normalized to 24-bit BI_RGB; raw image is not persisted)")

		for range ticker.C {
			bmp, sequence, sourceFormat, ok := readClipboardImageBMP()
			if sequence == 0 || sequence == lastSequence {
				continue
			}
			lastSequence = sequence

			if !ok || len(bmp) == 0 {
				continue
			}

			imageHash := hashClipboardImage(bmp)
			text, err := ocrClipboardBMP(bmp)
			if err != nil {
				log.Printf("clipboard screenshot OCR error source=%s error=%v", sourceFormat, err)
				continue
			}
			if strings.TrimSpace(text) == "" {
				continue
			}

			detections := detectSensitiveWithRules(text, customDetectionRules(api))
			if len(detections) == 0 {
				log.Printf("clipboard screenshot OCR completed source=%s result=no_sensitive_match", sourceFormat)
				continue
			}

			objectContext := buildObjectContext("clipboard-screenshot.bmp", "screenshot", detections)
			objectContext.DestinationTrust = "local"

			policies := map[string]PolicyDecision{}
			shouldClear := false
			for _, detection := range detections {
				if _, exists := policies[detection.Classification]; exists {
					continue
				}
				decision := resolvePolicy(api, detection.Classification, "screenshot")
				policies[detection.Classification] = decision
				if shouldMessagingClipboardBlock(decision.Action) {
					shouldClear = true
				}
			}

			cleared := false
			if shouldClear {
				cleared = clearClipboard()
				if cleared {
					log.Printf("screenshot clipboard enforcement: result=clipboard_cleared")
				} else {
					log.Printf("screenshot clipboard enforcement failed: clipboard could not be cleared")
				}
			}

			for _, detection := range detections {
				decision := policies[detection.Classification]
				blocked := cleared && shouldMessagingClipboardBlock(decision.Action)

				evidence := "clipboard_image_ocr+bitmap_normalized_24bpp+" + detection.Evidence
				if len(objectContext.ContextTags) > 0 {
					evidence += "+context:" + strings.Join(objectContext.ContextTags, ",")
				}
				if blocked {
					evidence += "+clipboard_cleared"
				}

				event := Event{
					EventID: fmt.Sprintf(
						"%s-%d",
						fingerprint("clipboard-screenshot|" + detection.Classification + "|" + detection.Value)[:12],
						time.Now().UnixNano(),
					),
					EndpointID:          endpointID,
					Hostname:            hostname,
					Username:            username,
					Process:             "windows-clipboard",
					ObjectPath:          "clipboard://screenshot",
					ObjectHash:          imageHash,
					Classification:      detection.Classification,
					Severity:            decision.Severity,
					Action:              decision.Action,
					MaskedValue:         mask(detection.Value),
					Fingerprint:         fingerprint(detection.Value),
					Channel:             "screenshot",
					Destination:         "clipboard",
					Policy:              decision.Policy,
					Evidence:            evidence,
					Blocked:             blocked,
					DocumentType:        "clipboard_image",
					DetectionCount:      objectContext.DetectionCount,
					ClassificationCount: objectContext.ClassificationCount,
					ContextTags:         objectContext.ContextTags,
					SensitiveFilename:   false,
					DestinationTrust:    "local",
				}

				if err := postJSON(api+"/events", event); err != nil {
					log.Printf("screenshot clipboard event error: %v", err)
					continue
				}
				log.Printf(
					"screenshot clipboard event: source=%s classification=%s action=%s blocked=%t",
					sourceFormat,
					detection.Classification,
					decision.Action,
					blocked,
				)
			}
		}
	}()
}
