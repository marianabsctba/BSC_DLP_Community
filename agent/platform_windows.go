//go:build windows

package main

import (
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"unsafe"
)

const driveRemovable = 2

type winGUID struct {
	Data1 uint32
	Data2 uint16
	Data3 uint16
	Data4 [8]byte
}

var (
	kernel32             = syscall.NewLazyDLL("kernel32.dll")
	shell32              = syscall.NewLazyDLL("shell32.dll")
	ole32                = syscall.NewLazyDLL("ole32.dll")
	procGetLogicalDrives = kernel32.NewProc("GetLogicalDrives")
	procGetDriveTypeW    = kernel32.NewProc("GetDriveTypeW")
	procSHGetKnownFolder = shell32.NewProc("SHGetKnownFolderPath")
	procCoTaskMemFree    = ole32.NewProc("CoTaskMemFree")

	folderDesktop     = winGUID{0xB4BFCC3A, 0xDB2C, 0x424C, [8]byte{0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41}}
	folderDocuments   = winGUID{0xFDD39AD0, 0x238F, 0x46AF, [8]byte{0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7}}
	folderDownloads   = winGUID{0x374DE290, 0x123F, 0x4565, [8]byte{0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B}}
	folderPictures    = winGUID{0x33E28130, 0x4E1E, 0x4676, [8]byte{0x83, 0x5A, 0x98, 0x39, 0x5C, 0x3B, 0xC3, 0xBB}}
	folderScreenshots = winGUID{0xB7BEDE81, 0xDF94, 0x4682, [8]byte{0xA7, 0xD8, 0x57, 0xA5, 0x26, 0x20, 0xB8, 0x6F}}
)

func platformOSName() string {
	return "windows"
}

func knownFolderPath(id *winGUID) string {
	var raw *uint16
	hr, _, _ := procSHGetKnownFolder.Call(
		uintptr(unsafe.Pointer(id)),
		uintptr(0),
		uintptr(0),
		uintptr(unsafe.Pointer(&raw)),
	)
	if hr != 0 || raw == nil {
		return ""
	}
	defer procCoTaskMemFree.Call(uintptr(unsafe.Pointer(raw)))

	// Windows paths are far below this bound; stop at the first UTF-16 NUL.
	chars := unsafe.Slice(raw, 32768)
	end := 0
	for end < len(chars) && chars[end] != 0 {
		end++
	}
	return syscall.UTF16ToString(chars[:end])
}

func addWatchIfDirectory(roots map[string]string, path, channel string) {
	if path == "" {
		return
	}

	path = filepath.Clean(path)
	info, err := os.Stat(path)
	if err != nil || !info.IsDir() {
		return
	}

	roots[path] = channel
}

func defaultWatchRoots() map[string]string {
	roots := map[string]string{}

	// SHGetKnownFolderPath respects localization, OneDrive redirection and
	// enterprise known-folder moves. This is safer than guessing English names.
	addWatchIfDirectory(roots, knownFolderPath(&folderDownloads), "download")
	addWatchIfDirectory(roots, knownFolderPath(&folderDesktop), "filesystem")
	addWatchIfDirectory(roots, knownFolderPath(&folderDocuments), "filesystem")

	screenshots := knownFolderPath(&folderScreenshots)
	addWatchIfDirectory(roots, screenshots, "screenshot")

	// Fallback for systems where FOLDERID_Screenshots is unavailable.
	pictures := knownFolderPath(&folderPictures)
	if screenshots == "" && pictures != "" {
		addWatchIfDirectory(roots, filepath.Join(pictures, "Screenshots"), "screenshot")
		addWatchIfDirectory(roots, filepath.Join(pictures, "Capturas de Tela"), "screenshot")
		addWatchIfDirectory(roots, filepath.Join(pictures, "Capturas de tela"), "screenshot")
	}

	return roots
}

func shouldCreateWatchRoot(string) bool {
	// Known folders are discovered from Windows. Never create a missing user
	// folder just to monitor it.
	return false
}

func platformRemovableRoots() map[string]string {
	roots := map[string]string{}

	mask, _, _ := procGetLogicalDrives.Call()
	if mask == 0 {
		return roots
	}

	for i := 0; i < 26; i++ {
		if mask&(1<<uintptr(i)) == 0 {
			continue
		}

		root := fmt.Sprintf("%c:\\", 'A'+i)
		rootPtr, err := syscall.UTF16PtrFromString(root)
		if err != nil {
			continue
		}

		driveType, _, _ := procGetDriveTypeW.Call(uintptr(unsafe.Pointer(rootPtr)))
		if driveType == driveRemovable {
			roots[filepath.Clean(root)] = "removable"
		}
	}

	return roots
}
