//go:build windows

package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	cfUnicodeText                  = 13
	processQueryLimitedInformation = 0x1000
	maxClipboardUTF16Units         = 262144
)

var (
	msgUser32   = syscall.NewLazyDLL("user32.dll")
	msgKernel32 = syscall.NewLazyDLL("kernel32.dll")

	procMsgGetForegroundWindow        = msgUser32.NewProc("GetForegroundWindow")
	procMsgGetWindowThreadProcessId   = msgUser32.NewProc("GetWindowThreadProcessId")
	procMsgGetClipboardSequenceNumber = msgUser32.NewProc("GetClipboardSequenceNumber")
	procMsgIsClipboardFormatAvailable = msgUser32.NewProc("IsClipboardFormatAvailable")
	procMsgOpenClipboard              = msgUser32.NewProc("OpenClipboard")
	procMsgCloseClipboard             = msgUser32.NewProc("CloseClipboard")
	procMsgGetClipboardData           = msgUser32.NewProc("GetClipboardData")
	procMsgEmptyClipboard             = msgUser32.NewProc("EmptyClipboard")

	procMsgOpenProcess                = msgKernel32.NewProc("OpenProcess")
	procMsgCloseHandle                = msgKernel32.NewProc("CloseHandle")
	procMsgQueryFullProcessImageNameW = msgKernel32.NewProc("QueryFullProcessImageNameW")
	procMsgGlobalLock                 = msgKernel32.NewProc("GlobalLock")
	procMsgGlobalUnlock               = msgKernel32.NewProc("GlobalUnlock")
	procMsgGlobalSize                 = msgKernel32.NewProc("GlobalSize")
)

func messagingSensorEnabled() bool {
	raw := strings.TrimSpace(strings.ToLower(os.Getenv("BSC_DLP_MESSAGING_SENSOR")))
	return raw != "0" && raw != "false" && raw != "off" && raw != "disabled"
}

func foregroundProcessName() string {
	hwnd, _, _ := procMsgGetForegroundWindow.Call()
	if hwnd == 0 {
		return ""
	}

	var pid uint32
	procMsgGetWindowThreadProcessId.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
	if pid == 0 {
		return ""
	}

	handle, _, _ := procMsgOpenProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
	if handle == 0 {
		return ""
	}
	defer procMsgCloseHandle.Call(handle)

	buf := make([]uint16, 32768)
	size := uint32(len(buf))
	ok, _, _ := procMsgQueryFullProcessImageNameW.Call(
		handle,
		0,
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(unsafe.Pointer(&size)),
	)
	if ok == 0 || size == 0 {
		return ""
	}

	return filepath.Base(syscall.UTF16ToString(buf[:size]))
}

func readClipboardText() (string, uint32, bool) {
	seq, _, _ := procMsgGetClipboardSequenceNumber.Call()
	available, _, _ := procMsgIsClipboardFormatAvailable.Call(cfUnicodeText)
	if available == 0 {
		return "", uint32(seq), false
	}

	opened, _, _ := procMsgOpenClipboard.Call(0)
	if opened == 0 {
		return "", uint32(seq), false
	}
	defer procMsgCloseClipboard.Call()

	handle, _, _ := procMsgGetClipboardData.Call(cfUnicodeText)
	if handle == 0 {
		return "", uint32(seq), false
	}

	ptr, _, _ := procMsgGlobalLock.Call(handle)
	if ptr == 0 {
		return "", uint32(seq), false
	}
	defer procMsgGlobalUnlock.Call(handle)

	sizeBytes, _, _ := procMsgGlobalSize.Call(handle)
	if sizeBytes < 2 {
		return "", uint32(seq), false
	}

	units := int(sizeBytes / 2)
	if units > maxClipboardUTF16Units {
		units = maxClipboardUTF16Units
	}
	chars := unsafe.Slice((*uint16)(unsafe.Pointer(ptr)), units)

	end := 0
	for end < len(chars) && chars[end] != 0 {
		end++
	}
	if end == 0 {
		return "", uint32(seq), false
	}

	return syscall.UTF16ToString(chars[:end]), uint32(seq), true
}

func clearClipboard() bool {
	opened, _, _ := procMsgOpenClipboard.Call(0)
	if opened == 0 {
		return false
	}
	defer procMsgCloseClipboard.Call()

	ok, _, _ := procMsgEmptyClipboard.Call()
	return ok != 0
}

func startMessagingClipboardSensor(api, endpointID, hostname, username string) {
	if !messagingSensorEnabled() {
		log.Printf("messaging clipboard sensor disabled by BSC_DLP_MESSAGING_SENSOR")
		return
	}

	go func() {
		ticker := time.NewTicker(550 * time.Millisecond)
		defer ticker.Stop()

		lastExposure := ""
		log.Printf("messaging clipboard sensor active (Windows desktop apps; raw clipboard is not stored)")

		for range ticker.C {
			processName := foregroundProcessName()
			provider := messagingProviderFromProcess(processName)
			if provider == "" {
				continue
			}

			text, sequence, ok := readClipboardText()
			if !ok || strings.TrimSpace(text) == "" {
				continue
			}

			contentFingerprint := fingerprint(text)
			exposureKey := fmt.Sprintf("%d|%s|%s", sequence, provider, contentFingerprint)
			if exposureKey == lastExposure {
				continue
			}
			lastExposure = exposureKey

			detections := detectSensitiveWithRules(text, customDetectionRules(api))
			if len(detections) == 0 {
				continue
			}

			objectContext := buildObjectContext("clipboard.txt", "messaging", detections)
			objectContext.DestinationTrust = "external"

			policies := map[string]PolicyDecision{}
			shouldClear := false
			for _, detection := range detections {
				if _, exists := policies[detection.Classification]; exists {
					continue
				}
				decision := resolvePolicy(api, detection.Classification, "messaging")
				policies[detection.Classification] = decision
				if shouldMessagingClipboardBlock(decision.Action) {
					shouldClear = true
				}
			}

			cleared := false
			if shouldClear {
				cleared = clearClipboard()
				if cleared {
					log.Printf("messaging clipboard enforcement: destination=%s process=%s result=clipboard_cleared", provider, processName)
				} else {
					log.Printf("messaging clipboard enforcement failed: destination=%s process=%s", provider, processName)
				}
			}

			for _, detection := range detections {
				decision := policies[detection.Classification]
				blocked := cleared && shouldMessagingClipboardBlock(decision.Action)

				evidence := "clipboard_sensitive+foreground_messaging_target:" + provider
				if blocked {
					evidence += "+clipboard_cleared"
				}

				event := Event{
					EventID: fmt.Sprintf(
						"%s-%d",
						fingerprint("clipboard|" + provider + "|" + detection.Classification + "|" + detection.Value)[:12],
						time.Now().UnixNano(),
					),
					EndpointID:          endpointID,
					Hostname:            hostname,
					Username:            username,
					Process:             processName,
					ObjectPath:          "clipboard://" + provider,
					ObjectHash:          contentFingerprint,
					Classification:      detection.Classification,
					Severity:            decision.Severity,
					Action:              decision.Action,
					MaskedValue:         mask(detection.Value),
					Fingerprint:         fingerprint(detection.Value),
					Channel:             "messaging",
					Destination:         provider,
					Policy:              decision.Policy,
					Evidence:            evidence,
					Blocked:             blocked,
					DocumentType:        "clipboard",
					DetectionCount:      objectContext.DetectionCount,
					ClassificationCount: objectContext.ClassificationCount,
					ContextTags:         objectContext.ContextTags,
					SensitiveFilename:   false,
					DestinationTrust:    "external",
				}

				if err := postJSON(api+"/events", event); err != nil {
					log.Printf("messaging event error: %v", err)
					continue
				}
				log.Printf("messaging exposure event: provider=%s classification=%s action=%s blocked=%t", provider, detection.Classification, decision.Action, blocked)
			}
		}
	}()
}
