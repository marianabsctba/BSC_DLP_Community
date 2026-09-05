import importlib
import sys
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def clients(tmp_path, monkeypatch):
    monkeypatch.setenv("BSC_DLP_HOME", str(tmp_path))
    sys.modules.pop("api.app", None)
    module = importlib.import_module("api.app")
    return TestClient(module.app), TestClient(module.app), TestClient(module.app)


def test_admin_agent_isolation_and_enrollment(clients):
    admin, agent, anonymous = clients

    assert anonymous.get("/api/v1/health").json()["status"] == "ok"
    assert anonymous.get("/api/v1/endpoints").status_code == 401

    response = admin.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "Senha-Forte-123!"},
    )
    assert response.status_code == 200

    response = admin.post(
        "/api/v1/admin/enrollment-token",
        json={"label": "Windows test", "ttl_minutes": 30, "uses": 1},
    )
    invite = response.json()["token"]

    endpoint_id = f"bsc-test-{uuid.uuid4().hex[:8]}"
    response = agent.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": invite},
        json={"endpoint_id": endpoint_id},
    )
    assert response.status_code == 200
    agent_token = response.json()["token"]

    assert agent.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": invite},
        json={"endpoint_id": "second-endpoint"},
    ).status_code == 401

    agent_headers = {"Authorization": f"Bearer {agent_token}"}
    assert agent.get("/api/v1/endpoints", headers=agent_headers).status_code == 401

    response = agent.post(
        "/api/v1/endpoints/heartbeat",
        headers=agent_headers,
        json={
            "endpoint_id": endpoint_id,
            "hostname": "WIN-TEST",
            "os": "windows",
            "agent_version": "0.5.4",
            "username": "tester",
        },
    )
    assert response.status_code == 200
    assert any(e["endpoint_id"] == endpoint_id for e in admin.get("/api/v1/endpoints").json())


def test_policy_event_risk_and_revoke(clients):
    admin, agent, _ = clients
    admin.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "Senha-Forte-123!"},
    )
    invite = admin.post(
        "/api/v1/admin/enrollment-token",
        json={"ttl_minutes": 30, "uses": 1},
    ).json()["token"]

    endpoint_id = f"bsc-test-{uuid.uuid4().hex[:8]}"
    token = agent.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": invite},
        json={"endpoint_id": endpoint_id},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    agent.post(
        "/api/v1/endpoints/heartbeat",
        headers=headers,
        json={"endpoint_id": endpoint_id, "hostname": "WIN-TEST", "os": "windows"},
    )

    policy = agent.get(
        "/api/v1/policies/resolve",
        headers=headers,
        params={"classification": "CPF", "channel": "removable"},
    )
    assert policy.status_code == 200
    assert policy.json()["action"] == "BLOCK"

    event_id = f"evt-{uuid.uuid4().hex}"
    response = agent.post(
        "/api/v1/events",
        headers=headers,
        json={
            "event_id": event_id,
            "endpoint_id": endpoint_id,
            "hostname": "WIN-TEST",
            "username": "tester",
            "object_path": r"E:\dados\clientes.pdf",
            "classification": "CPF",
            "severity": "CRITICAL",
            "action": "BLOCK",
            "channel": "removable",
            "policy": "CPF - Removable Media Block",
            "evidence": "cpf_checksum",
            "blocked": True,
            "document_type": "pdf",
        },
    )
    assert response.status_code == 200
    assert response.json()["risk_score"] >= 70

    stats = admin.get("/api/v1/stats").json()
    assert stats["blocked"] == 1
    assert stats["incidents"] == 1
    assert any(i["event_id"] == event_id for i in admin.get("/api/v1/incidents").json())

    assert admin.post(f"/api/v1/endpoints/{endpoint_id}/revoke").status_code == 200
    assert agent.post(
        "/api/v1/endpoints/heartbeat",
        headers=headers,
        json={"endpoint_id": endpoint_id, "hostname": "WIN-TEST"},
    ).status_code == 401


def test_filters_reports_and_custom_detectors(clients):
    admin, agent, _ = clients
    assert admin.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "Senha-Forte-123!"},
    ).status_code == 200
    invite = admin.post(
        "/api/v1/admin/enrollment-token", json={"ttl_minutes": 30, "uses": 1}
    ).json()["token"]
    endpoint_id = f"bsc-test-{uuid.uuid4().hex[:8]}"
    token = agent.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": invite},
        json={"endpoint_id": endpoint_id},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    rule = admin.post(
        "/api/v1/detection-rules",
        json={
            "name": "Contrato interno",
            "classification": "CONTRACT_ID",
            "pattern": r"CONTRATO-[0-9]{8}",
            "description": "IDs contratuais",
            "enabled": True,
        },
    )
    assert rule.status_code == 200
    rules = agent.get("/api/v1/agent/detection-rules", headers=headers)
    assert rules.status_code == 200
    assert any(r["classification"] == "CONTRACT_ID" for r in rules.json())

    for idx, (classification, channel, action, blocked) in enumerate([
        ("EMAIL_ADDRESS", "download", "ALERT", False),
        ("SECRET", "removable", "BLOCK", True),
        ("CREDENTIAL", "filesystem", "ALERT", False),
    ]):
        response = agent.post(
            "/api/v1/events",
            headers=headers,
            json={
                "event_id": f"evt-{uuid.uuid4().hex}",
                "endpoint_id": endpoint_id,
                "hostname": "WIN-FILTER",
                "username": "tester",
                "object_path": rf"C:\\dados\\arquivo-{idx}.txt",
                "classification": classification,
                "severity": "CRITICAL" if blocked else "HIGH",
                "action": action,
                "channel": channel,
                "policy": "Policy test",
                "evidence": "unit_test",
                "blocked": blocked,
                "document_type": "txt",
            },
        )
        assert response.status_code == 200

    filtered = admin.get(
        "/api/v1/events/query",
        params={"classification": "SECRET", "blocked": "true", "page": 1, "page_size": 10},
    )
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 1
    assert payload["items"][0]["classification"] == "SECRET"
    assert payload["page_size"] == 10

    incidents = admin.get("/api/v1/incidents/query", params={"page": 1, "page_size": 10})
    assert incidents.status_code == 200
    assert incidents.json()["total"] >= 1

    summary = admin.get("/api/v1/reports/summary")
    assert summary.status_code == 200
    assert summary.json()["metrics"]["events"] == 3
    assert summary.json()["metrics"]["blocked"] == 1

    csv_report = admin.get("/api/v1/reports/export.csv")
    assert csv_report.status_code == 200
    assert "text/csv" in csv_report.headers["content-type"]
    assert "Classificação" in csv_report.text

    pdf_report = admin.get("/api/v1/reports/export.pdf")
    assert pdf_report.status_code == 200
    assert "application/pdf" in pdf_report.headers["content-type"]
    assert pdf_report.content.startswith(b"%PDF")
    assert "attachment" in pdf_report.headers.get("content-disposition", "").lower()

    printable = admin.get("/api/v1/reports/print")
    assert printable.status_code == 200
    assert "Salvar como PDF" in printable.text


def test_trilingual_reports(clients):
    admin, _, _ = clients
    response = admin.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "Senha-Forte-123!"},
    )
    assert response.status_code == 200

    expectations = {
        "pt": ("Data,Risco", "Relatório de Proteção de Dados"),
        "en": ("Date,Risk", "Data Protection Report"),
        "es": ("Fecha,Riesgo", "Informe de Protección de Datos"),
    }
    for lang, (csv_prefix, print_title) in expectations.items():
        pdf_response = admin.get("/api/v1/reports/export.pdf", params={"lang": lang})
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"].startswith("application/pdf")
        assert pdf_response.content.startswith(b"%PDF")

        csv_response = admin.get("/api/v1/reports/export.csv", params={"lang": lang})
        assert csv_response.status_code == 200
        assert csv_response.content.decode("utf-8-sig").startswith(csv_prefix)

        print_response = admin.get("/api/v1/reports/print", params={"lang": lang})
        assert print_response.status_code == 200
        assert print_title in print_response.text


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
