#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def load(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Required file not found: {rel}")
    return path.read_text(encoding="utf-8")

def save(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[updated] {rel}")

def replace_once(text, old, new, label, required=True):
    if new in text:
        print(f"[skip] {label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        if required:
            raise RuntimeError(f"{label}: expected 1 exact match, found {count}")
        print(f"[skip] {label}: source pattern not found")
        return text
    return text.replace(old, new, 1)

def install_sources():
    for name in (
        "clipboard_image.go",
        "clipboard_image_test.go",
        "screenshot_clipboard_windows.go",
        "screenshot_clipboard_other.go",
    ):
        save(f"agent/{name}", (HERE / name).read_text(encoding="utf-8"))

def patch_agent():
    text = load("agent/main.go")
    text = text.replace('const version = "0.6.3"', 'const version = "0.6.4"', 1)

    call = "\tstartScreenshotClipboardSensor(api, endpointID, hostname, username)\n"
    if "startScreenshotClipboardSensor(api, endpointID, hostname, username)" not in text:
        anchor = "\tstartMessagingClipboardSensor(api, endpointID, hostname, username)\n"
        text = replace_once(text, anchor, anchor + call, "screenshot clipboard startup")

    save("agent/main.go", text)

def patch_backend():
    text = load("api/app.py")
    text = text.replace('version="0.6.3"', 'version="0.6.4"', 1)
    text = text.replace('"version": "0.6.3"', '"version": "0.6.4"', 1)

    if '"CNPJ - Screenshot Alert"' not in text:
        anchor = '        ("CPF - Screenshot Block", "CPF", "CRITICAL", "BLOCK", "screenshot", 10),\n'
        extra = (
            anchor
            + '        ("CPF-like - Screenshot Alert", "CPF_LIKE", "HIGH", "ALERT", "screenshot", 25),\n'
            + '        ("CNPJ - Screenshot Alert", "CNPJ", "HIGH", "ALERT", "screenshot", 25),\n'
            + '        ("Card Data - Screenshot Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "screenshot", 5),\n'
            + '        ("Secrets - Screenshot Block", "SECRET", "CRITICAL", "BLOCK", "screenshot", 5),\n'
            + '        ("Credentials - Screenshot Block", "CREDENTIAL", "CRITICAL", "BLOCK", "screenshot", 5),\n'
            + '        ("Bank Data - Screenshot Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "screenshot", 25),\n'
            + '        ("PIX - Screenshot Alert", "PIX_KEY", "HIGH", "ALERT", "screenshot", 25),\n'
        )
        text = replace_once(text, anchor, extra, "screenshot default policies")

    if '"clipboard_image_ocr"' not in text:
        marker = '        "browser_sensor": {\n'
        block = (
            '        "screenshot_clipboard_sensor": {\n'
            '            "capture_active_windows": True,\n'
            '            "capture_mode": "clipboard_image_ocr",\n'
            '            "formats": ["CF_DIBV5", "CF_DIB"],\n'
            '            "raw_image_persisted": False,\n'
            '            "temporary_bmp_deleted_after_ocr": True,\n'
            '            "clipboard_clear_on_block": True,\n'
            '            "pre_capture_prevention": False,\n'
            '            "note": "Windows clipboard screenshots (including Win+Shift+S when an image reaches the clipboard) are OCR-inspected locally. BLOCK clears the clipboard after detection; it does not prevent the pixels from being captured in the first place.",\n'
            '        },\n'
        )
        text = replace_once(text, marker, block + marker, "screenshot clipboard capabilities")

    save("api/app.py", text)

def patch_versions():
    dashboard = load("dashboard/index.html").replace("v0.6.3", "v0.6.4")
    save("dashboard/index.html", dashboard)

    launcher = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if launcher.exists():
        text = launcher.read_text(encoding="utf-8").replace("0.6.3", "0.6.4")
        launcher.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")

    manifest = ROOT / "browser-extension" / "manifest.json"
    if manifest.exists():
        text = manifest.read_text(encoding="utf-8").replace('"version": "0.6.3"', '"version": "0.6.4"', 1)
        manifest.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] browser-extension/manifest.json")

def patch_changelog():
    text = load("CHANGELOG.md")
    if "## 0.6.4 - 2026-09-05" not in text:
        entry = '''## 0.6.4 - 2026-09-05

- Novo **Windows Clipboard Screenshot OCR Sensor**.
- Imagens que chegam ao clipboard via captura de tela (incluindo fluxo `Win+Shift+S`) são convertidas temporariamente de DIB/DIBV5 para BMP e inspecionadas localmente por OCR.
- A imagem bruta não é enviada ao backend e o BMP temporário é removido imediatamente após o OCR.
- Eventos usam `channel=screenshot`, `destination=clipboard` e `document_type=clipboard_image`.
- Políticas `BLOCK`/`QUARANTINE` no canal screenshot podem limpar a imagem sensível do clipboard após a detecção.
- Novas políticas padrão de screenshot: CPF/cartão/segredos/credenciais com proteção forte; CPF-like/CNPJ/banking/PIX em ALERT.
- Capturas salvas em arquivo continuam usando o sensor de filesystem/screenshot já existente.
- Limite honesto: a v0.6.4 **não bloqueia o ato de capturar pixels antes da captura**; ela protege o artefato quando ele chega ao clipboard ou ao filesystem.

'''
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        save("CHANGELOG.md", text)

def main():
    if not (ROOT / "agent" / "evasion.go").exists():
        raise RuntimeError("v0.6.3 not found. Apply/pull v0.6.3 first.")
    install_sources()
    patch_agent()
    patch_backend()
    patch_versions()
    patch_changelog()
    print("")
    print("BSC DLP v0.6.4 Clipboard Screenshot OCR upgrade applied.")
    print("No commit was created.")
    print("Run TEST-V0.6.4.cmd.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
