#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def read(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Required file not found: {rel}")
    return path.read_text(encoding="utf-8")

def write(rel, content):
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

def patch_versions():
    main = read("agent/main.go")
    for old in ('const version = "0.6.4.1"', 'const version = "0.6.4"', 'const version = "0.6.3"'):
        if old in main:
            main = main.replace(old, 'const version = "0.6.5"', 1)
            break
    if 'const version = "0.6.5"' not in main:
        raise RuntimeError("agent version anchor not found")
    write("agent/main.go", main)

    dashboard = read("dashboard/index.html")
    for old in ("v0.6.4.1", "v0.6.4", "v0.6.3"):
        dashboard = dashboard.replace(old, "v0.6.5")
    write("dashboard/index.html", dashboard)

    launcher = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if launcher.exists():
        text = launcher.read_text(encoding="utf-8")
        for old in ("0.6.4.1", "0.6.4", "0.6.3"):
            text = text.replace(old, "0.6.5")
        launcher.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")

def patch_extractors():
    text = read("agent/extractors.go")
    old = '".txt", ".csv", ".json", ".xml", ".log", ".md", ".ini", ".conf", ".yaml", ".yml":'
    new = '".txt", ".csv", ".json", ".xml", ".log", ".md", ".ini", ".conf", ".yaml", ".yml", ".env", ".pem", ".key", ".sql":'
    text = text.replace(old, new)
    if ".env" not in text or ".pem" not in text or ".sql" not in text:
        raise RuntimeError("extractor text-extension patch failed")
    write("agent/extractors.go", text)

def patch_context():
    text = read("agent/context.go")
    old = 'case "messaging", "email", "ai":'
    new = 'case "messaging", "email", "ai", "browser_upload":'
    text = replace_once(text, old, new, "browser_upload destination trust")
    write("agent/context.go", text)

def patch_api():
    text = read("api/app.py")

    for old in ('version="0.6.4.1"', 'version="0.6.4"', 'version="0.6.3"'):
        text = text.replace(old, 'version="0.6.5"')
    for old in ('"version": "0.6.4.1"', '"version": "0.6.4"', '"version": "0.6.3"'):
        text = text.replace(old, '"version": "0.6.5"')

    if '"CPF - Browser Upload Block"' not in text:
        anchor = '        ("CPF - Messaging Alert", "CPF", "HIGH", "ALERT", "messaging", 25),\n'
        block = (
            '        ("CPF - Browser Upload Block", "CPF", "CRITICAL", "BLOCK", "browser_upload", 5),\n'
            '        ("CPF-like - Browser Upload Alert", "CPF_LIKE", "HIGH", "ALERT", "browser_upload", 20),\n'
            '        ("CNPJ - Browser Upload Alert", "CNPJ", "HIGH", "ALERT", "browser_upload", 20),\n'
            '        ("Card Data - Browser Upload Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "browser_upload", 5),\n'
            '        ("Secrets - Browser Upload Block", "SECRET", "CRITICAL", "BLOCK", "browser_upload", 5),\n'
            '        ("Credentials - Browser Upload Block", "CREDENTIAL", "CRITICAL", "BLOCK", "browser_upload", 5),\n'
            '        ("Bank Data - Browser Upload Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "browser_upload", 20),\n'
            '        ("PIX - Browser Upload Alert", "PIX_KEY", "HIGH", "ALERT", "browser_upload", 20),\n'
        )
        text = replace_once(text, anchor, block + anchor, "browser upload default policies")

    if '"browser_upload": 26,' not in text:
        anchor = '        "messaging": 24,\n'
        text = replace_once(
            text,
            anchor,
            anchor + '        "browser_upload": 26,\n',
            "browser upload risk channel",
        )

    if 'elif channel == "browser_upload":' not in text:
        anchor = '    elif channel == "messaging":\n        incident = "Possible sensitive-data exposure via messaging"\n'
        replacement = (
            '    elif channel == "browser_upload":\n'
            '        incident = "Possible sensitive browser upload"\n'
            + anchor
        )
        text = replace_once(text, anchor, replacement, "browser upload incident type")

    write("api/app.py", text)

def patch_changelog():
    text = read("CHANGELOG.md")
    if "## 0.6.5 - 2026-09-05" not in text:
        entry = """## 0.6.5 - 2026-09-05

- Novo **Generic Browser Upload DLP** no BSC DLP Browser Guard.
- A extensão passa a observar seletores de arquivo, drag & drop e paste de arquivo/imagem em páginas HTTP/HTTPS.
- Arquivos são enviados em chunks apenas para o bridge local `127.0.0.1:8765`; o conteúdo não sai do endpoint para inspeção.
- O bridge reconstrói um arquivo temporário local, reutiliza os extratores/OCR existentes e apaga o temporário ao final.
- Novo canal `browser_upload` com destino igual ao hostname da página e `destination_trust=external`.
- Policies padrão: CPF/cartão/secrets/credenciais em BLOCK; CPF-like/CNPJ/dados bancários/PIX em ALERT.
- Extensões textuais sensíveis `.env`, `.pem`, `.key` e `.sql` entram no pipeline de extração textual.
- WhatsApp Web text guard continua ativo e separado do pipeline de upload.
- Limite atual por arquivo: 25 MiB. Tipos ainda não suportados ficam fail-open com aviso; ZIP/7z/encrypted archives ficam para a próxima camada.
- Limite técnico: interceptação DOM é best-effort; aplicações web que processam arquivos fora dos eventos DOM convencionais podem exigir integração específica.

"""
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        write("CHANGELOG.md", text)

def copy_browser_sources():
    for name in ("content.js", "service-worker.js", "manifest.json", "upload-test.html"):
        source = HERE / name
        write(f"browser-extension/{name}", source.read_text(encoding="utf-8"))

    template = ROOT / "scripts" / "dev" / "browser-extension-template"
    if template.exists():
        for name in ("content.js", "service-worker.js", "manifest.json"):
            target = template / name
            target.write_text((HERE / name).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
            print(f"[updated] scripts/dev/browser-extension-template/{name}")

def main():
    if not (ROOT / "agent" / "screenshot_clipboard_windows.go").exists():
        raise RuntimeError("v0.6.4+ screenshot sensor not found. Apply prior upgrades first.")

    write("agent/browser_bridge.go", (HERE / "browser_bridge.go").read_text(encoding="utf-8"))
    copy_browser_sources()
    patch_versions()
    patch_extractors()
    patch_context()
    patch_api()
    patch_changelog()

    print("")
    print("BSC DLP v0.6.5 Generic Browser Upload DLP applied.")
    print("No commit was created.")
    print("Run TEST-V0.6.5.cmd.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
