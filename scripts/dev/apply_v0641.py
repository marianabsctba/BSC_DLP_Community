#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def read(rel):
    p = ROOT / rel
    if not p.exists():
        raise RuntimeError(f"Required file not found: {rel}")
    return p.read_text(encoding="utf-8")

def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    print(f"[updated] {rel}")

def main():
    if not (ROOT / "agent" / "screenshot_clipboard_windows.go").exists():
        raise RuntimeError("v0.6.4 screenshot clipboard sensor not found.")

    write(
        "agent/screenshot_clipboard_windows.go",
        (HERE / "screenshot_clipboard_windows.go").read_text(encoding="utf-8"),
    )

    main_go = read("agent/main.go")
    main_go = main_go.replace('const version = "0.6.4"', 'const version = "0.6.4.1"', 1)
    write("agent/main.go", main_go)

    app = read("api/app.py")
    app = app.replace('version="0.6.4"', 'version="0.6.4.1"', 1)
    app = app.replace('"version": "0.6.4"', '"version": "0.6.4.1"', 1)
    app = app.replace(
        '"capture_mode": "clipboard_image_ocr",',
        '"capture_mode": "clipboard_image_ocr_cf_bitmap_normalized",',
        1,
    )
    app = app.replace(
        '"formats": ["CF_DIBV5", "CF_DIB"],',
        '"formats": ["CF_BITMAP", "CF_DIBV5", "CF_DIB"],',
        1,
    )
    write("api/app.py", app)

    dashboard = read("dashboard/index.html").replace("v0.6.4", "v0.6.4.1")
    write("dashboard/index.html", dashboard)

    launcher = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if launcher.exists():
        text = launcher.read_text(encoding="utf-8").replace("0.6.4", "0.6.4.1")
        launcher.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")

    changelog = read("CHANGELOG.md")
    if "## 0.6.4.1 - 2026-09-05" not in changelog:
        entry = """## 0.6.4.1 - 2026-09-05

- Hotfix do OCR de screenshots no clipboard Windows.
- Corrige falha `pixReadMemBmp: cannot read compressed BMP files` observada com `CF_DIBV5`.
- O sensor agora prioriza `CF_BITMAP` e usa GDI `GetDIBits` para normalizar a captura para BMP 24-bit `BI_RGB` antes do Tesseract.
- DIB/DIBV5 permanece apenas como fallback seguro quando já estiver em formato não comprimido.
- Nenhuma imagem bruta é enviada ao backend; o BMP temporário continua sendo removido após OCR.

"""
        changelog = changelog.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        write("CHANGELOG.md", changelog)

    print("")
    print("BSC DLP v0.6.4.1 clipboard bitmap hotfix applied.")
    print("No commit was created.")
    print("Run TEST-HOTFIX-V0.6.4.1.cmd.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
