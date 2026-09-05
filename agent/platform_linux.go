//go:build linux

package main

import "path/filepath"

func platformOSName() string {
	return "linux"
}

func defaultWatchRoots() map[string]string {
	return map[string]string{
		filepath.Clean("/opt/bsc-dlp-watch"): "filesystem",
	}
}

func shouldCreateWatchRoot(root string) bool {
	return filepath.Clean(root) == filepath.Clean("/opt/bsc-dlp-watch")
}

func platformRemovableRoots() map[string]string {
	// Linux removable media remains configurable through BSC_DLP_WATCHES.
	// This preserves the currently deployed behavior on the VPS and avoids
	// assuming a distribution/desktop-specific mount layout.
	return map[string]string{}
}
