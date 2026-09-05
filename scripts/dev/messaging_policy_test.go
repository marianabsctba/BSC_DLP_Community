package main

import "testing"

func TestMessagingClipboardBlockingActions(t *testing.T) {
	for _, action := range []string{"BLOCK", "block", " QUARANTINE "} {
		if !shouldMessagingClipboardBlock(action) {
			t.Fatalf("expected %q to block clipboard", action)
		}
	}
	for _, action := range []string{"AUDIT", "ALERT", "ALLOW", ""} {
		if shouldMessagingClipboardBlock(action) {
			t.Fatalf("did not expect %q to block clipboard", action)
		}
	}
}
