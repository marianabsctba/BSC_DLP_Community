#!/usr/bin/env python3
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def load(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Required file not found: {rel}")
    return path.read_text(encoding="utf-8")

def save(rel, text):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"[updated] {rel}")

def add_sources():
    for name in ("browser_bridge.go", "browser_bridge_test.go"):
        save(f"agent/{name}", (HERE / name).read_text(encoding="utf-8"))

def install_extension():
    source = HERE / "browser-extension-template"
    target = ROOT / "browser-extension"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    print("[updated] browser-extension/")

def update_agent():
    text = load("agent/main.go")
    text = text.replace('const version = "0.6.1"', 'const version = "0.6.2"', 1)

    call = "startBrowserBridge(api, endpointID, hostname, username)"
    if call not in text:
        anchor = "\tstartMessagingClipboardSensor(api, endpointID, hostname, username)\n"
        if anchor not in text:
            raise RuntimeError("v0.6.1 messaging startup call not found")
        text = text.replace(anchor, anchor + "\tstartBrowserBridge(api, endpointID, hostname, username)\n", 1)
    save("agent/main.go", text)

def update_backend():
    text = load("api/app.py")
    text = text.replace('version="0.6.1"', 'version="0.6.2"', 1)
    text = text.replace('"version": "0.6.1"', '"version": "0.6.2"', 1)

    if '"browser_sensor"' not in text:
        marker = '        "messaging_sensor": {\n'
        idx = text.find(marker)
        if idx == -1:
            raise RuntimeError("messaging_sensor capability block not found")

        browser_block = '''        "browser_sensor": {
            "capture_active": True,
            "bridge": "http://127.0.0.1:8765",
            "destinations": ["whatsapp_web"],
            "outgoing_text": True,
            "paste": True,
            "send_click": True,
            "send_enter": True,
            "file_upload_capture_active": False,
            "chat_history_read": False,
            "raw_text_persisted": False,
            "failure_mode": "fail_open",
        },
'''
        text = text[:idx] + browser_block + text[idx:]

    save("api/app.py", text)

def update_dashboard():
    text = load("dashboard/index.html")
    text = text.replace("v0.6.1", "v0.6.2")
    save("dashboard/index.html", text)

def update_launcher():
    path = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if path.exists():
        text = path.read_text(encoding="utf-8").replace("0.6.1", "0.6.2")
        path.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")

def update_changelog():
    text = load("CHANGELOG.md")
    if "## 0.6.2 - 2026-09-05" not in text:
        entry = '''## 0.6.2 - 2026-09-05

- Novo Browser Guard MV3 para WhatsApp Web em Chrome/Edge.
- Extensão inspeciona somente conteúdo de saída do composer: paste, clique em enviar e Enter.
- A extensão não lê histórico de chats e não persiste texto bruto.
- Bridge local no agente (`127.0.0.1:8765`) reutiliza o mesmo detector, classificador e motor de políticas do endpoint.
- Eventos usam `channel=messaging` e `destination=whatsapp_web`.
- Políticas BLOCK/QUARANTINE impedem o paste/envio antes da ação do WhatsApp Web.
- Em indisponibilidade do bridge local, o comportamento padrão é fail-open com aviso visual.
- Upload de arquivos pelo navegador ainda não é captura ativa nesta versão.

'''
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        save("CHANGELOG.md", text)

def main():
    if not (ROOT / "agent" / "messaging_policy.go").exists():
        raise RuntimeError("v0.6.1 not found. Apply v0.6.1 first.")
    add_sources()
    install_extension()
    update_agent()
    update_backend()
    update_dashboard()
    update_launcher()
    update_changelog()
    print("")
    print("BSC DLP v0.6.2 WhatsApp Web upgrade applied.")
    print("No commit was created.")
    print("Run TEST-V0.6.2.cmd.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
