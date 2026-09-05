#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "agent" / "v04_test.go"

def fail(msg):
    print(f"[ERROR] {msg}")
    raise SystemExit(1)

if not TARGET.exists():
    fail(f"File not found: {TARGET}")

original = TARGET.read_text(encoding="utf-8")
text = original

helper = '''
func TestMain(m *testing.M) {
\tif os.Getenv("BSC_DLP_FAKE_TESSERACT") == "1" {
\t\targs := strings.Join(os.Args[1:], " ")
\t\tif strings.Contains(args, "por+eng") {
\t\t\t_, _ = os.Stderr.WriteString("missing por language\\\\n")
\t\t\tos.Exit(1)
\t\t}
\t\t_, _ = os.Stdout.WriteString("CPF 529.982.247-25\\\\n")
\t\tos.Exit(0)
\t}
\tos.Exit(m.Run())
}

'''

if "func TestMain(m *testing.M)" not in text:
    marker = "func TestDetectCNPJAndCard(t *testing.T) {"
    if marker not in text:
        fail("Could not locate first test function")
    text = text.replace(marker, helper + marker, 1)

replacement = '''\tfake, err := os.Executable()
\tif err != nil {
\t\tt.Fatal(err)
\t}
\tt.Setenv("BSC_DLP_FAKE_TESSERACT", "1")
\tt.Setenv("BSC_DLP_TESSERACT", fake)
'''

old1 = '''\tfake := filepath.Join(dir, "fake-tesseract")
\tscript := `#!/bin/sh
case "$*" in
  *por+eng*) echo "missing por language" >&2; exit 1 ;;
  *) echo "CPF 529.982.247-25" ;;
esac
`
\tif err := os.WriteFile(fake, []byte(script), 0700); err != nil {
\t\tt.Fatal(err)
\t}
\tt.Setenv("BSC_DLP_TESSERACT", fake)
'''

old2 = '''\tfake := filepath.Join(dir, "fake-tesseract")
\tscript := `#!/bin/sh
echo "CPF 529.982.247-25"
`
\tif err := os.WriteFile(fake, []byte(script), 0700); err != nil {
\t\tt.Fatal(err)
\t}
\tt.Setenv("BSC_DLP_TESSERACT", fake)
'''

count1 = text.count(old1)
count2 = text.count(old2)

if count1 == 1:
    text = text.replace(old1, replacement, 1)
elif "BSC_DLP_FAKE_TESSERACT" not in original:
    fail(f"Could not safely locate first fake-tesseract block (matches={count1})")

if count2 == 1:
    text = text.replace(old2, replacement, 1)
elif original.count("fake-tesseract") > 0 and "BSC_DLP_FAKE_TESSERACT" not in original:
    fail(f"Could not safely locate second fake-tesseract block (matches={count2})")

if text == original:
    print("[BSC DLP] Windows OCR test hotfix appears to be already applied.")
    raise SystemExit(0)

backup = TARGET.with_name("v04_test.go.bak-before-windows-ocr-test-fix")
if not backup.exists():
    backup.write_text(original, encoding="utf-8")

TARGET.write_text(text, encoding="utf-8", newline="\n")

print("[BSC DLP] Windows OCR test hotfix applied.")
print(f"Updated: {TARGET}")
print("The fake Tesseract now uses the Go test executable itself, so the OCR fallback test is cross-platform.")
