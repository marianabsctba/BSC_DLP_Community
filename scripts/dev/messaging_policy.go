package main

import "strings"

func shouldMessagingClipboardBlock(action string) bool {
	switch strings.ToUpper(strings.TrimSpace(action)) {
	case "BLOCK", "QUARANTINE":
		return true
	default:
		return false
	}
}
