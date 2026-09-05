package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func endpointQuarantineRoot() string {
	if configured := strings.TrimSpace(os.Getenv("BSC_DLP_QUARANTINE")); configured != "" {
		return configured
	}
	cfg, err := os.UserConfigDir()
	if err != nil || cfg == "" {
		return filepath.Join(os.TempDir(), "BSC-DLP-Quarantine")
	}
	return filepath.Join(cfg, "BSC-DLP-Community", "quarantine")
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	ok := false
	defer func() {
		_ = out.Close()
		if !ok {
			_ = os.Remove(dst)
		}
	}()

	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	if err := out.Sync(); err != nil {
		return err
	}
	ok = true
	return nil
}

func enforcePath(path, action string) (bool, string) {
	action = strings.ToUpper(strings.TrimSpace(action))
	if action != "BLOCK" && action != "QUARANTINE" {
		return false, ""
	}

	info, err := os.Stat(path)
	if err != nil || info.IsDir() {
		if err == nil {
			err = fmt.Errorf("object is a directory")
		}
		return false, fmt.Sprintf("enforcement_failed:%v", err)
	}

	root := endpointQuarantineRoot()
	if err := os.MkdirAll(root, 0700); err != nil {
		return false, fmt.Sprintf("enforcement_failed:%v", err)
	}

	suffix := fingerprint(path + time.Now().String())[:10]
	name := fmt.Sprintf("%s-%s-%s", time.Now().UTC().Format("20060102T150405Z"), suffix, filepath.Base(path))
	dst := filepath.Join(root, name)

	// Copy+remove works across volumes (important for USB/removable media).
	if err := copyFile(path, dst); err != nil {
		return false, fmt.Sprintf("enforcement_failed:%v", err)
	}
	if err := os.Remove(path); err != nil {
		_ = os.Remove(dst)
		return false, fmt.Sprintf("enforcement_failed:%v", err)
	}

	return true, "endpoint_quarantine"
}
