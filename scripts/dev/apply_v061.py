#!/usr/bin/env python3
from pathlib import Path
import re

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

def add_sources():
    if not (ROOT / "agent" / "context.go").exists():
        raise RuntimeError("v0.6 context.go not found. Apply v0.6 first.")
    for name in (
        "messaging_policy.go",
        "messaging_sensor_windows.go",
        "messaging_sensor_other.go",
        "messaging_policy_test.go",
    ):
        save(f"agent/{name}", (HERE / name).read_text(encoding="utf-8"))

def update_agent():
    text = load("agent/main.go")
    text = text.replace('const version = "0.6.0"', 'const version = "0.6.1"', 1)

    if "startMessagingClipboardSensor(api, endpointID, hostname, username)" not in text:
        anchor = "\n\twatcher, err := fsnotify.NewWatcher()\n"
        if anchor not in text:
            raise RuntimeError("Could not locate watcher startup in agent/main.go")
        text = text.replace(
            anchor,
            "\n\tstartMessagingClipboardSensor(api, endpointID, hostname, username)\n\n\twatcher, err := fsnotify.NewWatcher()\n",
            1,
        )
    save("agent/main.go", text)

def update_backend():
    text = load("api/app.py")

    if "def utc_iso(" not in text:
        helper = '''def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    value = _ensure_utc(value)
    if value is None:
        return None
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def host_iso(value: Optional[datetime]) -> Optional[str]:
    value = _ensure_utc(value)
    if value is None:
        return None
    return value.astimezone().isoformat(timespec="seconds")


'''
        marker = "def endpoint_is_online(last_seen) -> bool:\n"
        if marker not in text:
            raise RuntimeError("Could not locate time helper insertion point")
        text = text.replace(marker, helper + marker, 1)

    text = text.replace('version="0.6.0"', 'version="0.6.1"', 1)
    text = text.replace('"version": "0.6.0"', '"version": "0.6.1"', 1)

    if '"Card Data - Messaging Block"' not in text:
        old = '''        ("Credentials - Download Alert", "CREDENTIAL", "HIGH", "ALERT", "download", 30),
'''
        new = '''        ("Credentials - Download Alert", "CREDENTIAL", "HIGH", "ALERT", "download", 30),
        ("CPF - Messaging Alert", "CPF", "HIGH", "ALERT", "messaging", 25),
        ("CNPJ - Messaging Alert", "CNPJ", "HIGH", "ALERT", "messaging", 25),
        ("Bank Data - Messaging Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "messaging", 20),
        ("PIX - Messaging Alert", "PIX_KEY", "HIGH", "ALERT", "messaging", 20),
        ("Card Data - Messaging Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "messaging", 5),
        ("Secrets - Messaging Block", "SECRET", "CRITICAL", "BLOCK", "messaging", 5),
        ("Credentials - Messaging Block", "CREDENTIAL", "CRITICAL", "BLOCK", "messaging", 5),
'''
        text = replace_once(text, old, new, "default messaging policies")

    text = text.replace('"last_seen": row.last_seen,', '"last_seen": utc_iso(row.last_seen),', 1)
    text = text.replace('"created_at": rule.created_at,', '"created_at": utc_iso(rule.created_at),', 1)
    text = text.replace('"timestamp": r.timestamp,', '"timestamp": utc_iso(r.timestamp),', 1)

    if '"server_time_utc"' not in text:
        text = replace_once(
            text,
            '        "database": "sqlite",\n',
            '        "database": "sqlite",\n        "server_time_utc": utc_iso(now()),\n        "server_time_local": datetime.now().astimezone().isoformat(timespec="seconds"),\n',
            "health time diagnostics",
        )

    text = text.replace(
        '    generated_at = now().astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")\n',
        '    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")\n',
        1,
    )
    text = text.replace(
        '        timestamp = row.timestamp.isoformat(timespec="seconds") if row.timestamp else ""\n',
        '        timestamp = host_iso(row.timestamp) or ""\n',
        1,
    )
    text = text.replace(
        '                r.timestamp.isoformat() if r.timestamp else "", int(r.risk_score or 0), _csv_safe(r.endpoint_id), _csv_safe(r.hostname),\n',
        '                host_iso(r.timestamp) or "", int(r.risk_score or 0), _csv_safe(r.endpoint_id), _csv_safe(r.hostname),\n',
        1,
    )

    if 'item["first_seen"] = utc_iso' not in text:
        old = '''        offset = (page - 1) * page_size
        return {
            "items": items[offset:offset + page_size],
            "total": total,
'''
        new = '''        offset = (page - 1) * page_size
        page_items = items[offset:offset + page_size]
        for item in page_items:
            item["first_seen"] = utc_iso(item["first_seen"])
            item["last_seen"] = utc_iso(item["last_seen"])
        return {
            "items": page_items,
            "total": total,
'''
        text = replace_once(text, old, new, "correlated incident timezone", required=False)

    text = text.replace(
        '"channels": ["filesystem", "download", "screenshot", "removable"],',
        '"channels": ["filesystem", "download", "screenshot", "removable", "messaging"],',
        1,
    )
    text = text.replace(
        '''            "active": ["filesystem", "download", "screenshot", "removable"],
            "foundation": ["clipboard", "messaging", "email", "ai"],
''',
        '''            "active": ["filesystem", "download", "screenshot", "removable"],
            "active_windows": ["messaging"],
            "foundation": ["clipboard", "email", "ai"],
''',
        1,
    )

    text = re.sub(
        r'        "messaging_foundation": \{\n.*?\n        \},\n        "context_engine": \{',
        '''        "messaging_sensor": {
            "capture_active_windows": True,
            "capture_mode": "clipboard_foreground_target",
            "providers": ["whatsapp", "teams", "slack", "telegram", "discord"],
            "raw_clipboard_stored": False,
            "clipboard_block_supported": True,
            "web_capture_active": False,
            "file_upload_capture_active": False,
            "note": "Windows desktop messaging protection observes sensitive clipboard exposure to recognized foreground messaging apps. It does not read chat messages or decrypt traffic.",
        },
        "context_engine": {''',
        text,
        count=1,
        flags=re.S,
    )

    save("api/app.py", text)

def update_dashboard():
    text = load("dashboard/index.html")
    text = text.replace("v0.6.0", "v0.6.1")

    if "<option>messaging</option>" not in text:
        text = text.replace(
            "<option>removable</option>",
            "<option>removable</option><option>messaging</option>",
        )

    if 'value="messaging"' not in text:
        text = text.replace(
            '<option value="removable">USB / Removable</option>',
            '<option value="removable">USB / Removable</option><option value="messaging">Messaging / WhatsApp Desktop</option>',
            1,
        )

    save("dashboard/index.html", text)

def update_tests():
    tests = load("tests/test_api_integration.py")
    if "test_explicit_utc_timestamp_serialization" not in tests:
        tests += r'''

def test_explicit_utc_timestamp_serialization(clients):
    admin, agent, anonymous = clients
    assert admin.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "Senha-Forte-123!"},
    ).status_code == 200

    health = anonymous.get("/api/v1/health").json()
    assert health["server_time_utc"].endswith("Z")
    assert health["server_time_local"]

    invite = admin.post(
        "/api/v1/admin/enrollment-token",
        json={"ttl_minutes": 30, "uses": 1},
    ).json()["token"]
    endpoint_id = f"bsc-time-{uuid.uuid4().hex[:8]}"
    token = agent.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": invite},
        json={"endpoint_id": endpoint_id},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert agent.post(
        "/api/v1/endpoints/heartbeat",
        headers=headers,
        json={"endpoint_id": endpoint_id, "hostname": "WIN-TIME", "os": "windows"},
    ).status_code == 200

    assert agent.post(
        "/api/v1/events",
        headers=headers,
        json={
            "event_id": f"evt-{uuid.uuid4().hex}",
            "endpoint_id": endpoint_id,
            "hostname": "WIN-TIME",
            "classification": "EMAIL_ADDRESS",
            "severity": "MEDIUM",
            "action": "AUDIT",
            "channel": "filesystem",
        },
    ).status_code == 200

    payload = admin.get(
        "/api/v1/events/query",
        params={"endpoint": endpoint_id, "page": 1, "page_size": 10},
    ).json()
    assert payload["items"]
    assert payload["items"][0]["timestamp"].endswith("Z")

    endpoints = admin.get("/api/v1/endpoints").json()
    endpoint = next(row for row in endpoints if row["endpoint_id"] == endpoint_id)
    assert endpoint["last_seen"].endswith("Z")
'''
        save("tests/test_api_integration.py", tests)

def update_changelog():
    text = load("CHANGELOG.md")
    if "## 0.6.1 - 2026-09-05" not in text:
        entry = '''## 0.6.1 - 2026-09-05

- Windows Messaging Clipboard Sensor para WhatsApp Desktop, Teams, Slack, Telegram e Discord.
- Inspeção local do clipboard somente quando um app de mensageria reconhecido está em foreground.
- Conteúdo bruto do clipboard não é persistido; somente valores mascarados/fingerprinted.
- Políticas BLOCK/QUARANTINE no canal messaging podem limpar o clipboard antes do paste.
- PII/banking em ALERT por padrão; cartão/segredos/credenciais em BLOCK para mensageria.
- Não lê mensagens, não quebra E2EE e não intercepta chats.
- WhatsApp Web e upload de arquivos ainda não são captura ativa nesta versão.
- Timestamps corrigidos: API emite UTC com Z explícito e a console converte para o horário local do host/browser.
- PDF/CSV exibem horário local do host.
- /api/v1/health informa server_time_utc e server_time_local.

'''
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        save("CHANGELOG.md", text)

def update_launcher():
    path = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if path.exists():
        text = path.read_text(encoding="utf-8").replace("0.6.0", "0.6.1")
        path.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")

def main():
    add_sources()
    update_agent()
    update_backend()
    update_dashboard()
    update_tests()
    update_changelog()
    update_launcher()
    print("")
    print("BSC DLP v0.6.1 Messaging + Host Time upgrade applied.")
    print("No branch and no commit were created.")
    print("Run TEST-V0.6.1.cmd before committing.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
