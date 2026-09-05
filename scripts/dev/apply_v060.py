#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

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

def replace_once(text, old, new, label):
    if new in text:
        print(f"[skip] {label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 exact match, found {count}")
    return text.replace(old, new, 1)

def sub_once(text, pattern, replacement, label):
    if replacement.strip() in text:
        print(f"[skip] {label}: already applied")
        return text
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.M | re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 regex match, found {count}")
    return new

def update_detectors():
    text = load("agent/detectors.go")
    text = re.sub(r'^var cepContextRegex = .*\n', '', text, count=1, flags=re.M)
    text = re.sub(
        r'\n\tfor _, value := range captureMatches\(cepContextRegex, text, 1, 100\) \{\n\t\tadd\("CEP_BR", value, "cep_context"\)\n\t\}',
        '',
        text,
        count=1,
    )
    if "cepContextRegex" in text or 'add("CEP_BR"' in text:
        raise RuntimeError("Could not safely remove the native CEP detector")
    save("agent/detectors.go", text)

def update_agent():
    save("agent/context.go", (HERE / "context.go").read_text(encoding="utf-8"))
    save("agent/context_test.go", (HERE / "context_test.go").read_text(encoding="utf-8"))

    text = load("agent/main.go")
    text = text.replace('const version = "0.5.4"', 'const version = "0.6.0"', 1)

    text = replace_once(
        text,
        '''\tBlocked        bool   `json:"blocked"`
\tDocumentType   string `json:"document_type,omitempty"`
''',
        '''\tBlocked             bool     `json:"blocked"`
\tDocumentType        string   `json:"document_type,omitempty"`
\tDestination         string   `json:"destination,omitempty"`
\tDetectionCount      int      `json:"detection_count,omitempty"`
\tClassificationCount int      `json:"classification_count,omitempty"`
\tContextTags         []string `json:"context_tags,omitempty"`
\tSensitiveFilename   bool     `json:"sensitive_filename,omitempty"`
\tDestinationTrust    string   `json:"destination_trust,omitempty"`
''',
        "agent event context fields",
    )

    text = replace_once(
        text,
        '''\tdetections := detectSensitiveWithRules(text, customDetectionRules(api))
\tif len(detections) == 0 {
\t\treturn
\t}

\tobjectHash := fileHash(path)
''',
        '''\tdetections := detectSensitiveWithRules(text, customDetectionRules(api))
\tif len(detections) == 0 {
\t\treturn
\t}

\tobjectContext := buildObjectContext(path, channel, detections)
\tobjectHash := fileHash(path)
''',
        "agent object context",
    )

    text = replace_once(
        text,
        '''\t\tdecision := policyByClassification[detection.Classification]
\t\tevidence := inspection + "+" + detection.Evidence
\t\tif extra := enforcementEvidence[detection.Classification]; extra != "" {
''',
        '''\t\tdecision := policyByClassification[detection.Classification]
\t\tevidence := inspection + "+" + detection.Evidence
\t\tif len(objectContext.ContextTags) > 0 {
\t\t\tevidence += "+context:" + strings.Join(objectContext.ContextTags, ",")
\t\t}
\t\tif extra := enforcementEvidence[detection.Classification]; extra != "" {
''',
        "agent context evidence",
    )

    text = replace_once(
        text,
        '''\t\t\tEvidence:       evidence,
\t\t\tBlocked:        blockedByClassification[detection.Classification],
\t\t\tDocumentType:   docType,
''',
        '''\t\t\tEvidence:            evidence,
\t\t\tBlocked:             blockedByClassification[detection.Classification],
\t\t\tDocumentType:        docType,
\t\t\tDetectionCount:      objectContext.DetectionCount,
\t\t\tClassificationCount: objectContext.ClassificationCount,
\t\t\tContextTags:          objectContext.ContextTags,
\t\t\tSensitiveFilename:    objectContext.SensitiveFilename,
\t\t\tDestinationTrust:     objectContext.DestinationTrust,
''',
        "agent event metadata",
    )
    save("agent/main.go", text)

def update_backend():
    text = load("api/app.py")
    if "import json\n" not in text:
        text = text.replace("import io\n", "import io\nimport json\n", 1)

    text = replace_once(
        text,
        '''    risk_score = Column(Integer, default=0)
    incident_type = Column(String(128))
    document_type = Column(String(64))
''',
        '''    risk_score = Column(Integer, default=0)
    incident_type = Column(String(128))
    incident_key = Column(String(64), index=True)
    document_type = Column(String(64))
    detection_count = Column(Integer, default=1)
    classification_count = Column(Integer, default=1)
    context_tags = Column(Text)
    sensitive_filename = Column(Boolean, default=False)
    destination_trust = Column(String(32))
    risk_reasons = Column(Text)
''',
        "database context columns",
    )

    text = replace_once(
        text,
        '''        "risk_score": "INTEGER DEFAULT 0",
        "incident_type": "VARCHAR(128)",
        "document_type": "VARCHAR(64)",
''',
        '''        "risk_score": "INTEGER DEFAULT 0",
        "incident_type": "VARCHAR(128)",
        "incident_key": "VARCHAR(64)",
        "document_type": "VARCHAR(64)",
        "detection_count": "INTEGER DEFAULT 1",
        "classification_count": "INTEGER DEFAULT 1",
        "context_tags": "TEXT",
        "sensitive_filename": "BOOLEAN DEFAULT 0",
        "destination_trust": "VARCHAR(32)",
        "risk_reasons": "TEXT",
''',
        "SQLite migration fields",
    )

    text = replace_once(
        text,
        '''    blocked: bool = False
    document_type: Optional[str] = None
''',
        '''    blocked: bool = False
    document_type: Optional[str] = None
    detection_count: int = Field(default=1, ge=1, le=10000)
    classification_count: int = Field(default=1, ge=1, le=256)
    context_tags: list[str] = Field(default_factory=list)
    sensitive_filename: bool = False
    destination_trust: Optional[str] = None
''',
        "EventIn context fields",
    )

    risk_block = '''def risk_for_event(
    body: EventIn,
    recent_count: int,
    recent_object_count: int = 0,
) -> tuple[int, str, list[str]]:
    reasons: list[str] = []
    severity = body.severity.upper()
    score = {"LOW": 5, "MEDIUM": 15, "HIGH": 30, "CRITICAL": 45}.get(severity, 15)
    reasons.append(f"severity:{severity}")

    channel = body.channel.lower()
    score += {
        "removable": 24,
        "screenshot": 18,
        "download": 10,
        "messaging": 24,
        "email": 22,
        "ai": 26,
        "clipboard": 16,
        "filesystem": 3,
    }.get(channel, 6)
    reasons.append(f"channel:{channel}")

    action = body.action.upper()
    if action in {"BLOCK", "QUARANTINE"}:
        score += 12
        reasons.append(f"action:{action}")
    elif action == "ALERT":
        score += 6
        reasons.append("action:ALERT")
    if body.blocked:
        score += 3
        reasons.append("enforcement:blocked")

    detections = max(int(body.detection_count or 1), 1)
    if detections >= 50:
        score += 20
        reasons.append("volume:50+")
    elif detections >= 10:
        score += 12
        reasons.append("volume:10+")
    elif detections >= 3:
        score += 5
        reasons.append("volume:3+")

    classes = max(int(body.classification_count or 1), 1)
    if classes >= 3:
        score += 12
        reasons.append("co_occurrence:3+")
    elif classes >= 2:
        score += 7
        reasons.append("co_occurrence:2+")

    tags = {str(tag).strip().lower() for tag in body.context_tags if str(tag).strip()}
    if body.sensitive_filename or "sensitive_filename" in tags:
        score += 8
        reasons.append("sensitive_filename")
    if "high_value_extension" in tags:
        score += 6
        reasons.append("high_value_extension")

    trust = (body.destination_trust or "unknown").strip().lower()
    if trust in {"external", "untrusted"}:
        score += 12
        reasons.append(f"destination:{trust}")
    elif trust in {"internal", "trusted", "local"}:
        reasons.append(f"destination:{trust}")

    if recent_count >= 15:
        score += 15
        reasons.append("burst:15+")
    elif recent_count >= 6:
        score += 10
        reasons.append("burst:6+")
    elif recent_count >= 3:
        score += 5
        reasons.append("burst:3+")

    if recent_object_count >= 10:
        score += 10
        reasons.append("objects:10+")
    elif recent_object_count >= 3:
        score += 5
        reasons.append("objects:3+")

    score = min(score, 100)

    if channel == "removable" and detections >= 10:
        incident = "Bulk sensitive-data transfer to removable media"
    elif channel == "removable":
        incident = "Possible removable-media exfiltration"
    elif channel == "messaging":
        incident = "Possible sensitive-data exposure via messaging"
    elif channel == "screenshot":
        incident = "Sensitive screenshot activity"
    elif channel == "download" and classes >= 2:
        incident = "Multi-class sensitive download activity"
    elif channel == "download":
        incident = "Sensitive download activity"
    elif channel == "email":
        incident = "Possible external email exfiltration"
    elif channel == "ai":
        incident = "Possible AI data exposure"
    elif detections >= 10:
        incident = "Bulk sensitive-data activity"
    elif classes >= 2:
        incident = "Multi-class sensitive data activity"
    elif recent_count >= 6:
        incident = "Unusual sensitive-data burst"
    else:
        incident = "Sensitive data activity"

    return score, incident, reasons


def incident_key_for_event(body: EventIn, incident_type: str, event_time: datetime) -> str:
    bucket = int(event_time.timestamp()) // 300
    basis = "|".join([
        body.endpoint_id,
        body.username or "",
        body.channel.lower(),
        body.destination or "",
        incident_type,
        str(bucket),
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
'''

    text = sub_once(
        text,
        r'def risk_for_event\(body: EventIn, recent_count: int\) -> tuple\[int, str\]:\n.*?\n    return score, incident\n',
        risk_block.rstrip(),
        "risk engine",
    )

    text = text.replace('version="0.5.4"', 'version="0.6.0"', 1)
    text = text.replace('"version": "0.5.4"', '"version": "0.6.0"', 1)

    text = replace_once(
        text,
        '''        burst_since = now() - timedelta(minutes=5)
        recent_count = db.query(Event).filter(
            Event.endpoint_id == body.endpoint_id,
            Event.timestamp >= burst_since,
        ).count()
        risk_score, incident_type = risk_for_event(body, recent_count)
        event = Event(
            event_id=body.event_id,
            timestamp=now(),
''',
        '''        event_time = now()
        burst_since = event_time - timedelta(minutes=5)
        recent_rows = db.query(Event).filter(
            Event.endpoint_id == body.endpoint_id,
            Event.timestamp >= burst_since,
        ).all()
        recent_count = len(recent_rows)
        recent_object_count = len({
            row.object_hash or row.object_path or row.event_id
            for row in recent_rows
        })
        risk_score, incident_type, risk_reasons = risk_for_event(
            body, recent_count, recent_object_count
        )
        incident_key = incident_key_for_event(body, incident_type, event_time)
        event = Event(
            event_id=body.event_id,
            timestamp=event_time,
''',
        "event ingestion context",
    )

    text = replace_once(
        text,
        '''            risk_score=risk_score,
            incident_type=incident_type,
            document_type=(body.document_type or "").lower() or None,
''',
        '''            risk_score=risk_score,
            incident_type=incident_type,
            incident_key=incident_key,
            document_type=(body.document_type or "").lower() or None,
            detection_count=body.detection_count,
            classification_count=body.classification_count,
            context_tags=json.dumps(body.context_tags[:32], ensure_ascii=False),
            sensitive_filename=body.sensitive_filename,
            destination_trust=(body.destination_trust or "unknown").lower(),
            risk_reasons=json.dumps(risk_reasons, ensure_ascii=False),
''',
        "persist context",
    )

    text = replace_once(
        text,
        '''            "risk_score": risk_score,
            "incident_type": incident_type,
''',
        '''            "risk_score": risk_score,
            "incident_type": incident_type,
            "incident_key": incident_key,
            "risk_reasons": risk_reasons,
''',
        "event response reasons",
    )

    helper = '''def _json_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


'''
    if "def _json_list(value)" not in text:
        text = text.replace("def serialize_event(r: Event) -> dict:\n", helper + "def serialize_event(r: Event) -> dict:\n", 1)

    text = replace_once(
        text,
        '''        "risk_score": int(r.risk_score or 0),
        "incident_type": r.incident_type,
        "document_type": r.document_type,
''',
        '''        "risk_score": int(r.risk_score or 0),
        "incident_type": r.incident_type,
        "incident_key": r.incident_key,
        "document_type": r.document_type,
        "detection_count": int(r.detection_count or 1),
        "classification_count": int(r.classification_count or 1),
        "context_tags": _json_list(r.context_tags),
        "sensitive_filename": bool(r.sensitive_filename),
        "destination_trust": r.destination_trust or "unknown",
        "risk_reasons": _json_list(r.risk_reasons),
''',
        "serialize context",
    )

    correlated = '''@app.get("/api/v1/incidents/correlated")
def correlated_incidents(
    request: Request,
    page: int = 1,
    page_size: int = 25,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 40,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
):
    require_admin(request)
    db = SessionLocal()
    try:
        query = _event_query(
            db,
            incident_only=True,
            endpoint=endpoint,
            classification=classification,
            channel=channel,
            severity=severity,
            action=action,
            blocked=blocked,
            risk_min=max(risk_min, 40),
            start=start,
            end=end,
            q=q,
        )
        rows = query.order_by(Event.timestamp.desc()).limit(10000).all()
        groups = {}
        for row in rows:
            key = row.incident_key or f"event:{row.id}"
            group = groups.setdefault(key, {
                "incident_key": key,
                "incident_type": row.incident_type,
                "endpoint_id": row.endpoint_id,
                "hostname": row.hostname,
                "username": row.username,
                "channel": row.channel,
                "destination": row.destination,
                "event_count": 0,
                "max_risk": 0,
                "first_seen": row.timestamp,
                "last_seen": row.timestamp,
                "blocked": False,
                "classifications": set(),
                "objects": set(),
                "risk_reasons": set(),
            })
            group["event_count"] += 1
            group["max_risk"] = max(group["max_risk"], int(row.risk_score or 0))
            group["first_seen"] = min(group["first_seen"], row.timestamp)
            group["last_seen"] = max(group["last_seen"], row.timestamp)
            group["blocked"] = group["blocked"] or bool(row.blocked)
            if row.classification:
                group["classifications"].add(row.classification)
            group["objects"].add(row.object_hash or row.object_path or row.event_id)
            group["risk_reasons"].update(_json_list(row.risk_reasons))

        items = []
        for group in groups.values():
            group["classifications"] = sorted(group["classifications"])
            group["object_count"] = len(group.pop("objects"))
            group["risk_reasons"] = sorted(group["risk_reasons"])
            items.append(group)

        items.sort(key=lambda item: (item["max_risk"], item["last_seen"]), reverse=True)
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 25), 10), 100)
        total = len(items)
        pages = max((total + page_size - 1) // page_size, 1)
        page = min(page, pages)
        offset = (page - 1) * page_size
        return {
            "items": items[offset:offset + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    finally:
        db.close()


'''
    if '@app.get("/api/v1/incidents/correlated")' not in text:
        marker = 'def _report_rows(db, *, incident_only: bool = False, **filters):'
        if marker not in text:
            raise RuntimeError("Could not find report marker for correlated incidents API")
        text = text.replace(marker, correlated + marker, 1)

    text = text.replace(
        '''            "CPF", "CNPJ", "CREDIT_CARD", "EMAIL_ADDRESS", "RG_BR", "CEP_BR", "PHONE_BR",
            "PIX_KEY", "BANK_ACCOUNT", "PASSPORT", "CREDENTIAL", "SECRET"
''',
        '''            "CPF", "CNPJ", "CREDIT_CARD", "EMAIL_ADDRESS", "RG_BR", "PHONE_BR",
            "PIX_KEY", "BANK_ACCOUNT", "PASSPORT", "CREDENTIAL", "SECRET"
''',
        1,
    )

    text = replace_once(
        text,
        '''        "channels": ["filesystem", "download", "screenshot", "removable"],
        "classifiers": [
''',
        '''        "channels": ["filesystem", "download", "screenshot", "removable"],
        "channel_status": {
            "active": ["filesystem", "download", "screenshot", "removable"],
            "foundation": ["clipboard", "messaging", "email", "ai"],
        },
        "messaging_foundation": {
            "capture_active": False,
            "providers": ["whatsapp", "teams", "slack", "telegram", "discord"],
            "note": "Messaging providers are modeled for future endpoint/browser capture adapters; this version does not claim active message interception.",
        },
        "context_engine": {
            "co_occurrence": True,
            "bulk_detection": True,
            "sensitive_filename": True,
            "destination_trust": True,
            "explainable_risk": True,
            "incident_correlation": True,
            "correlation_window_minutes": 5,
        },
        "optional_custom_examples": ["CEP_BR"],
        "classifiers": [
''',
        "capability model",
    )

    preview_model = '''class RiskPreviewIn(EventIn):
    pass


'''
    if "class RiskPreviewIn(EventIn)" not in text:
        text = text.replace("class DetectionRuleIn(BaseModel):\n", preview_model + "class DetectionRuleIn(BaseModel):\n", 1)

    preview_api = '''@app.post("/api/v1/admin/risk-preview")
def risk_preview(body: RiskPreviewIn, request: Request):
    require_admin(request)
    score, incident_type, reasons = risk_for_event(body, 0, 0)
    return {
        "risk_score": score,
        "incident_type": incident_type,
        "risk_reasons": reasons,
        "note": "Preview only. No event was stored and no enforcement action was executed.",
    }


'''
    if '@app.post("/api/v1/admin/risk-preview")' not in text:
        marker = '@app.post("/api/v1/events")'
        if marker not in text:
            raise RuntimeError("Could not find events endpoint for risk preview API")
        text = text.replace(marker, preview_api + marker, 1)

    save("api/app.py", text)

def update_tests():
    text = load("agent/v05_test.go")
    text = text.replace("CEP: 80000-000\n", "")
    text = text.replace('\t\t"CEP_BR":        false,\n', "")
    save("agent/v05_test.go", text)

    tests = load("tests/test_api_integration.py")
    if "test_context_engine_preview_and_correlation" not in tests:
        tests += r'''

def test_context_engine_preview_and_correlation(clients):
    admin, agent, _ = clients
    assert admin.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "Senha-Forte-123!"},
    ).status_code == 200

    preview = admin.post(
        "/api/v1/admin/risk-preview",
        json={
            "event_id": "preview-only",
            "endpoint_id": "preview-endpoint",
            "classification": "CPF",
            "severity": "HIGH",
            "action": "BLOCK",
            "channel": "messaging",
            "destination": "whatsapp",
            "blocked": False,
            "detection_count": 80,
            "classification_count": 3,
            "context_tags": ["mass_data", "co_occurrence", "sensitive_filename"],
            "sensitive_filename": True,
            "destination_trust": "external",
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["risk_score"] >= 90
    assert "volume:50+" in body["risk_reasons"]
    assert "co_occurrence:3+" in body["risk_reasons"]
    assert "destination:external" in body["risk_reasons"]

    invite = admin.post(
        "/api/v1/admin/enrollment-token",
        json={"ttl_minutes": 30, "uses": 1},
    ).json()["token"]
    endpoint_id = f"bsc-context-{uuid.uuid4().hex[:8]}"
    token = agent.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": invite},
        json={"endpoint_id": endpoint_id},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    base = {
        "endpoint_id": endpoint_id,
        "hostname": "WIN-CONTEXT",
        "username": "tester",
        "object_path": r"E:\\dados\\folha_pagamento.xlsx",
        "severity": "CRITICAL",
        "action": "BLOCK",
        "channel": "removable",
        "blocked": True,
        "detection_count": 60,
        "classification_count": 2,
        "context_tags": ["mass_data", "co_occurrence", "sensitive_filename"],
        "sensitive_filename": True,
        "destination_trust": "untrusted",
    }

    first = agent.post(
        "/api/v1/events",
        headers=headers,
        json={"event_id": f"evt-{uuid.uuid4().hex}", "classification": "CPF", **base},
    )
    second = agent.post(
        "/api/v1/events",
        headers=headers,
        json={"event_id": f"evt-{uuid.uuid4().hex}", "classification": "BANK_ACCOUNT", **base},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["incident_key"] == second.json()["incident_key"]

    correlated = admin.get(
        "/api/v1/incidents/correlated",
        params={"endpoint": endpoint_id, "page": 1, "page_size": 10},
    )
    assert correlated.status_code == 200
    assert any(
        item["incident_key"] == first.json()["incident_key"]
        and item["event_count"] >= 2
        for item in correlated.json()["items"]
    )
'''
        save("tests/test_api_integration.py", tests)

def update_dashboard():
    text = load("dashboard/index.html")
    text = text.replace("<option>CEP_BR</option>", "")
    text = text.replace("v0.5.4", "v0.6.0")

    new_function = '''async function loadIncidents(page=incidentPage){incidentPage=page;const d=await api('/incidents/correlated?'+qsFrom('inc',{page,incidents:true}).toString());incidentPage=d.page;$('incidentList').innerHTML=d.items.length?d.items.map(e=>`<div class="incident"><div class="risk-number">${Number(e.max_risk||0)}</div><div><strong>${esc(e.incident_type||tr('Atividade com dados sensíveis'))}</strong><small>${esc(e.hostname||e.endpoint_id)} · ${(e.classifications||[]).map(esc).join(', ')} · ${esc(e.channel)} · ${Number(e.event_count||0)} evento(s) · ${Number(e.object_count||0)} objeto(s)</small><small>${(e.risk_reasons||[]).map(esc).join(' · ')}</small></div><div class="incident-meta">${e.blocked?`<span class="badge block">${tr('BLOQUEADO')}</span>`:`<span class="badge alert">ALERT</span>`}<small>${esc(when(e.last_seen))}</small></div></div>`).join(''):`<div class="empty">${tr('Nenhum incidente com estes filtros.')}</div>`;$('incidentPager').innerHTML=pagerHTML(d.page,d.pages,d.total,'loadIncidents');$('incidentCountLabel').textContent=currentLang==='en'?`${d.total} incident${d.total===1?'':'s'}`:currentLang==='es'?`${d.total} incidente${d.total===1?'':'s'}`:`${d.total} incidente${d.total===1?'':'s'}`}
'''
    text = sub_once(
        text,
        r'async function loadIncidents\(page=incidentPage\)\{.*?\}\nfunction applyIncidentFilters',
        new_function + 'function applyIncidentFilters',
        "correlated incident UI",
    )
    save("dashboard/index.html", text)

def update_versions_and_changelog():
    start = load("scripts/windows/Start-Community.ps1").replace("0.5.4", "0.6.0")
    save("scripts/windows/Start-Community.ps1", start)

    changelog = load("CHANGELOG.md")
    if "## 0.6.0 - 2026-09-05" not in changelog:
        entry = '''## 0.6.0 - 2026-09-05

- Novo **Context-Aware DLP Engine** com co-occurrence, volume, nomes/extensões sensíveis e destination trust.
- CEP removido dos detectores nativos; continua possível como detector customizado.
- Risk score passa a ser explicável por `risk_reasons`.
- Incidentes recebem `incident_key` e podem ser correlacionados em janela de 5 minutos sem perder eventos brutos.
- Console de Incidentes passa a consumir a visão correlacionada.
- Adicionado `risk-preview` para testar cenários de política sem gravar evento nem executar enforcement.
- Fundamentos de canais futuros `clipboard`, `messaging`, `email` e `ai`.
- WhatsApp, Teams, Slack, Telegram e Discord são modelados como destinos futuros de mensageria, mas **captura ativa de mensagens não é anunciada nesta versão**.
- Mantidos como canais ativos: filesystem, download, screenshot e removable.

'''
        changelog = changelog.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        save("CHANGELOG.md", changelog)

def main():
    update_detectors()
    update_agent()
    update_backend()
    update_tests()
    update_dashboard()
    update_versions_and_changelog()
    print("")
    print("BSC DLP v0.6.0 source upgrade applied.")
    print("No branch and no commit were created.")
    print("Run TEST-V0.6.cmd before committing.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
