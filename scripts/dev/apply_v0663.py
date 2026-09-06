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


def install_agent_sources():
    for name in (
        "browser_guard_presence.go",
        "browser_guard_presence_windows.go",
        "browser_guard_presence_other.go",
        "browser_guard_presence_test.go",
    ):
        write(f"agent/{name}", (HERE / name).read_text(encoding="utf-8"))


def patch_browser_bridge():
    text = read("agent/browser_bridge.go")
    text = text.replace(
        '"version":"0.6.5","file_upload":true',
        '"version":"0.6.6.3","file_upload":true,"guard_presence":true',
        1,
    )

    route = '''
\tmux.HandleFunc("/v1/guard/heartbeat", func(w http.ResponseWriter, r *http.Request) {
\t\tif r.Method != http.MethodPost {
\t\t\thttp.Error(w, "method not allowed", http.StatusMethodNotAllowed)
\t\t\treturn
\t\t}
\t\tif !requireBrowserExtension(w, r) {
\t\t\treturn
\t\t}

\t\tr.Body = http.MaxBytesReader(w, r.Body, 32*1024)
\t\tdefer r.Body.Close()

\t\tvar body BrowserGuardHeartbeatRequest
\t\tif err := json.NewDecoder(r.Body).Decode(&body); err != nil {
\t\t\thttp.Error(w, "invalid json", http.StatusBadRequest)
\t\t\treturn
\t\t}
\t\tif err := recordBrowserGuardHeartbeat(api, endpointID, hostname, username, body); err != nil {
\t\t\thttp.Error(w, err.Error(), http.StatusBadRequest)
\t\t\treturn
\t\t}

\t\twriteBrowserJSON(w, map[string]any{
\t\t\t"status": "ok",
\t\t\t"browser": normalizeGuardBrowser(body.Browser),
\t\t\t"heartbeat_timeout_seconds": int(browserGuardHeartbeatTimeout / time.Second),
\t\t})
\t})
'''
    if '/v1/guard/heartbeat' not in text:
        anchor = '\n\tmux.HandleFunc("/v1/inspect", func(w http.ResponseWriter, r *http.Request) {'
        if anchor not in text:
            raise RuntimeError("browser bridge inspect route anchor not found")
        text = text.replace(anchor, route + anchor, 1)

    if 'startBrowserGuardPresenceWatch(api, endpointID, hostname, username)' not in text:
        anchor = '\n\tserver := &http.Server{'
        if anchor not in text:
            raise RuntimeError("browser bridge server anchor not found")
        text = text.replace(anchor, '\n\tstartBrowserGuardPresenceWatch(api, endpointID, hostname, username)\n' + anchor, 1)

    text = text.replace(
        'browser DLP bridge active http://%s (text + generic file upload)',
        'browser DLP bridge active http://%s (text + generic file upload + guard presence watch)',
        1,
    )
    write("agent/browser_bridge.go", text)


def install_extension_runtime():
    write("browser-extension/service-worker.js", (HERE / "service-worker.js").read_text(encoding="utf-8"))
    write("browser-extension/manifest.json", (HERE / "manifest.json").read_text(encoding="utf-8"))


def patch_agent_version():
    text = read("agent/main.go")
    for old in ('const version = "0.6.6"', 'const version = "0.6.6.1"', 'const version = "0.6.6.2"'):
        if old in text:
            text = text.replace(old, 'const version = "0.6.6.3"', 1)
            break
    if 'const version = "0.6.6.3"' not in text:
        raise RuntimeError("agent version anchor not found")
    write("agent/main.go", text)


def patch_api():
    text = read("api/app.py")
    text = text.replace('version="0.6.6"', 'version="0.6.6.3"', 1)
    text = text.replace('"version": "0.6.6"', '"version": "0.6.6.3"', 1)

    if '"browser_guard": 28,' not in text:
        anchor = '        "browser_upload": 26,\n'
        if anchor not in text:
            raise RuntimeError("risk channel anchor not found")
        text = text.replace(anchor, anchor + '        "browser_guard": 28,\n', 1)

    if 'Browser Guard protection disabled or missing' not in text:
        anchor = '    if channel == "removable" and detections >= 10:\n'
        block = '''    if channel == "browser_guard" and body.classification.upper() == "BROWSER_GUARD_DISABLED_OR_MISSING":
        incident = "Browser Guard protection disabled or missing"
    elif channel == "browser_guard" and body.classification.upper() == "BROWSER_GUARD_RESTORED":
        incident = "Browser Guard protection restored"
    elif channel == "removable" and detections >= 10:
'''
        if anchor not in text:
            raise RuntimeError("incident routing anchor not found")
        text = text.replace(anchor, block, 1)

    write("api/app.py", text)


def patch_dashboard():
    text = read("dashboard/index.html")
    text = text.replace("v0.6.6", "v0.6.6.3")

    old = '<option>removable</option><option>messaging</option>'
    new = '<option>removable</option><option>messaging</option><option>browser_upload</option><option>browser_guard</option>'
    text = text.replace(old, new)

    policy_channel_old = '<option value="messaging">Messaging / WhatsApp Desktop</option>'
    policy_channel_new = policy_channel_old + '<option value="browser_upload">Browser Upload</option><option value="browser_guard">Browser Guard Presence</option>'
    text = text.replace(policy_channel_old, policy_channel_new)

    policy_class_old = '<option>CREDENTIAL</option><option>SECRET</option>'
    policy_class_new = policy_class_old + '<option>BROWSER_GUARD_DISABLED_OR_MISSING</option><option>BROWSER_GUARD_RESTORED</option>'
    text = text.replace(policy_class_old, policy_class_new)

    write("dashboard/index.html", text)


def patch_launcher():
    path = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for old in ("0.6.6.2", "0.6.6.1", "0.6.6"):
        text = text.replace(old, "0.6.6.3")
    path.write_text(text, encoding="utf-8", newline="\n")
    print("[updated] scripts/windows/Start-Community.ps1")


def patch_changelog():
    text = read("CHANGELOG.md")
    if "## 0.6.6.3 - 2026-09-06" not in text:
        entry = '''## 0.6.6.3 - 2026-09-06

- Browser Guard Presence Watch para Chrome, Edge e Firefox.
- A extensão envia heartbeat local periódico ao bridge do agente.
- O agente verifica se o navegador está em execução e alerta quando o heartbeat da extensão desaparece.
- Novo evento `BROWSER_GUARD_DISABLED_OR_MISSING` em `channel=browser_guard`, severidade HIGH e ação ALERT.
- Novo evento `BROWSER_GUARD_RESTORED` quando a proteção retorna.
- Anti-spam por transição de estado: um alerta por perda, um evento por restauração.
- Navegador fechado não é tratado como extensão desabilitada.
- Edge/Chrome usam MV3 service worker; Firefox mantém `background.scripts` compatibility path.
- Browser Upload e Browser Guard adicionados aos filtros de canal do dashboard.

'''
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        write("CHANGELOG.md", text)


def main():
    if not (ROOT / "agent" / "browser_bridge.go").exists():
        raise RuntimeError("Browser Guard bridge not found")
    if not (ROOT / "browser-extension" / "service-worker.js").exists():
        raise RuntimeError("Browser Guard extension not found")

    install_agent_sources()
    patch_browser_bridge()
    install_extension_runtime()
    patch_agent_version()
    patch_api()
    patch_dashboard()
    patch_launcher()
    patch_changelog()

    print("")
    print("BSC DLP v0.6.6.3 Browser Guard Presence & Tamper Detection applied.")
    print("No commit was created.")
    print("Run TEST-V0.6.6.3.cmd.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
