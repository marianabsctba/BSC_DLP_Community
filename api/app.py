#!/usr/bin/env python3

from datetime import datetime, timedelta, timezone
import csv
import html
import io
import json
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import re
import sys
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_ROOT = _application_root()
DATA_ROOT = Path(os.getenv("BSC_DLP_HOME", str(APP_ROOT))).expanduser().resolve()
DATA_DIR = DATA_ROOT / "data"
CONFIG_DIR = DATA_ROOT / "config"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = os.getenv("BSC_DLP_DB_PATH", str(DATA_DIR / "dlp.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

SESSION_COOKIE = "bsc_dlp_admin"
SESSION_HOURS = 12


def now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
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


def endpoint_is_online(last_seen) -> bool:
    if not last_seen:
        return False
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (now() - last_seen).total_seconds() <= 90


class Endpoint(Base):
    __tablename__ = "endpoints"
    id = Column(Integer, primary_key=True)
    endpoint_id = Column(String(128), unique=True, index=True, nullable=False)
    hostname = Column(String(255), nullable=False)
    os = Column(String(255))
    agent_version = Column(String(64))
    username = Column(String(255))
    last_seen = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, default=True)


class EndpointCredential(Base):
    __tablename__ = "endpoint_credentials"
    id = Column(Integer, primary_key=True)
    endpoint_id = Column(String(128), unique=True, index=True, nullable=False)
    token_hash = Column(String(64), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class EnrollmentInvite(Base):
    __tablename__ = "enrollment_invites"
    id = Column(Integer, primary_key=True)
    label = Column(String(255))
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    uses_left = Column(Integer, nullable=False, default=1)
    revoked = Column(Boolean, default=False, nullable=False)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    salt = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    id = Column(Integer, primary_key=True)
    username = Column(String(128), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    classification = Column(String(128), index=True, nullable=False)
    severity = Column(String(32), nullable=False, default="MEDIUM")
    action = Column(String(32), nullable=False, default="AUDIT")
    enabled = Column(Boolean, default=True)
    channel = Column(String(64), default="filesystem")
    priority = Column(Integer, default=100)




class DetectionRule(Base):
    __tablename__ = "detection_rules"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    classification = Column(String(128), index=True, nullable=False)
    pattern = Column(Text, nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(128), unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    endpoint_id = Column(String(128), index=True, nullable=False)
    hostname = Column(String(255))
    username = Column(String(255))
    process = Column(String(255))
    object_path = Column(Text)
    object_hash = Column(String(128))
    object_size_bytes = Column(Integer, default=0)
    classification = Column(String(128), index=True)
    severity = Column(String(32), index=True)
    action = Column(String(32), index=True)
    masked_value = Column(Text)
    fingerprint = Column(String(128), index=True)
    channel = Column(String(64), default="filesystem")
    destination = Column(Text)
    policy = Column(String(255))
    evidence = Column(Text)
    blocked = Column(Boolean, default=False)
    risk_score = Column(Integer, default=0)
    incident_type = Column(String(128))
    incident_key = Column(String(64), index=True)
    document_type = Column(String(64))
    detection_count = Column(Integer, default=1)
    classification_count = Column(Integer, default=1)
    context_tags = Column(Text)
    sensitive_filename = Column(Boolean, default=False)
    destination_trust = Column(String(32))
    risk_reasons = Column(Text)


Base.metadata.create_all(engine)


def migrate_sqlite() -> None:
    """Small additive migration for users upgrading a Community database."""
    inspector = inspect(engine)
    if "events" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("events")}
    additions = {
        "risk_score": "INTEGER DEFAULT 0",
        "incident_type": "VARCHAR(128)",
        "incident_key": "VARCHAR(64)",
        "document_type": "VARCHAR(64)",
        "object_size_bytes": "INTEGER DEFAULT 0",
        "detection_count": "INTEGER DEFAULT 1",
        "classification_count": "INTEGER DEFAULT 1",
        "context_tags": "TEXT",
        "sensitive_filename": "BOOLEAN DEFAULT 0",
        "destination_trust": "VARCHAR(32)",
        "risk_reasons": "TEXT",
    }
    with engine.begin() as conn:
        for column, ddl in additions.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE events ADD COLUMN {column} {ddl}"))


migrate_sqlite()


def seed_default_policies() -> None:
    defaults = [
        ("CPF - Filesystem Audit", "CPF", "MEDIUM", "AUDIT", "filesystem", 100),
        ("CPF - Download Protection", "CPF", "HIGH", "ALERT", "download", 20),
        ("CPF - Screenshot Block", "CPF", "CRITICAL", "BLOCK", "screenshot", 10),
        ("CPF-like - Screenshot Alert", "CPF_LIKE", "HIGH", "ALERT", "screenshot", 25),
        ("CNPJ - Screenshot Alert", "CNPJ", "HIGH", "ALERT", "screenshot", 25),
        ("Card Data - Screenshot Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "screenshot", 5),
        ("Secrets - Screenshot Block", "SECRET", "CRITICAL", "BLOCK", "screenshot", 5),
        ("Credentials - Screenshot Block", "CREDENTIAL", "CRITICAL", "BLOCK", "screenshot", 5),
        ("Bank Data - Screenshot Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "screenshot", 25),
        ("PIX - Screenshot Alert", "PIX_KEY", "HIGH", "ALERT", "screenshot", 25),
        ("CPF - Removable Media Block", "CPF", "CRITICAL", "BLOCK", "removable", 10),
        ("CNPJ - Removable Media Block", "CNPJ", "CRITICAL", "BLOCK", "removable", 10),
        ("Card Data - Removable Media Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "removable", 10),
        ("Secrets - Filesystem Alert", "SECRET", "HIGH", "ALERT", "filesystem", 30),
        ("Secrets - Download Alert", "SECRET", "HIGH", "ALERT", "download", 30),
        ("Secrets - Removable Media Block", "SECRET", "CRITICAL", "BLOCK", "removable", 10),
        ("Credentials - Removable Media Block", "CREDENTIAL", "CRITICAL", "BLOCK", "removable", 10),
        ("Credentials - Download Alert", "CREDENTIAL", "HIGH", "ALERT", "download", 30),
        ("CPF - Browser Upload Block", "CPF", "CRITICAL", "BLOCK", "browser_upload", 5),
        ("RG - Browser Upload Alert", "RG_BR", "HIGH", "ALERT", "browser_upload", 20),
        ("Passport - Browser Upload Alert", "PASSPORT", "HIGH", "ALERT", "browser_upload", 20),
        ("CNH - Browser Upload Alert", "CNH_BR", "HIGH", "ALERT", "browser_upload", 20),
        ("CNS - Browser Upload Alert", "CNS_BR", "CRITICAL", "ALERT", "browser_upload", 15),
        ("Email - Browser Upload Alert", "EMAIL_ADDRESS", "MEDIUM", "ALERT", "browser_upload", 40),
        ("Phone - Browser Upload Alert", "PHONE_BR", "MEDIUM", "ALERT", "browser_upload", 40),
        ("Birth Date - Browser Upload Alert", "DATE_OF_BIRTH", "MEDIUM", "ALERT", "browser_upload", 40),
        ("Physical Address - Browser Upload Alert", "PHYSICAL_ADDRESS", "MEDIUM", "ALERT", "browser_upload", 40),
        ("Card Security Code - Browser Upload Block", "CARD_SECURITY_CODE", "CRITICAL", "BLOCK", "browser_upload", 1),
        ("Card PIN - Browser Upload Block", "CARD_PIN", "CRITICAL", "BLOCK", "browser_upload", 1),
        ("Card Track Data - Browser Upload Block", "CARD_TRACK_DATA", "CRITICAL", "BLOCK", "browser_upload", 1),
        ("CPF-like - Browser Upload Alert", "CPF_LIKE", "HIGH", "ALERT", "browser_upload", 20),
        ("CNPJ - Browser Upload Alert", "CNPJ", "HIGH", "ALERT", "browser_upload", 20),
        ("Card Data - Browser Upload Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "browser_upload", 5),
        ("Secrets - Browser Upload Block", "SECRET", "CRITICAL", "BLOCK", "browser_upload", 5),
        ("Credentials - Browser Upload Block", "CREDENTIAL", "CRITICAL", "BLOCK", "browser_upload", 5),
        ("Bank Data - Browser Upload Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "browser_upload", 20),
        ("PIX - Browser Upload Alert", "PIX_KEY", "HIGH", "ALERT", "browser_upload", 20),
        ("CPF - Messaging Alert", "CPF", "HIGH", "ALERT", "messaging", 25),
        ("CPF-like - Messaging Alert", "CPF_LIKE", "HIGH", "ALERT", "messaging", 30),
        ("CNPJ - Messaging Alert", "CNPJ", "HIGH", "ALERT", "messaging", 25),
        ("Bank Data - Messaging Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "messaging", 20),
        ("PIX - Messaging Alert", "PIX_KEY", "HIGH", "ALERT", "messaging", 20),
        ("Card Data - Messaging Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "messaging", 5),
        ("Card Security Code - Messaging Block", "CARD_SECURITY_CODE", "CRITICAL", "BLOCK", "messaging", 1),
        ("Card PIN - Messaging Block", "CARD_PIN", "CRITICAL", "BLOCK", "messaging", 1),
        ("Card Track Data - Messaging Block", "CARD_TRACK_DATA", "CRITICAL", "BLOCK", "messaging", 1),
        ("RG - Messaging Alert", "RG_BR", "HIGH", "ALERT", "messaging", 25),
        ("Passport - Messaging Alert", "PASSPORT", "HIGH", "ALERT", "messaging", 25),
        ("CNH - Messaging Alert", "CNH_BR", "HIGH", "ALERT", "messaging", 25),
        ("Email - Messaging Alert", "EMAIL_ADDRESS", "MEDIUM", "ALERT", "messaging", 40),
        ("Phone - Messaging Alert", "PHONE_BR", "MEDIUM", "ALERT", "messaging", 40),
        ("Secrets - Messaging Block", "SECRET", "CRITICAL", "BLOCK", "messaging", 5),
        ("Credentials - Messaging Block", "CREDENTIAL", "CRITICAL", "BLOCK", "messaging", 5),
        ("CPF - AI Prompt Block", "CPF", "CRITICAL", "BLOCK", "ai_prompt", 5),
        ("CPF-like - AI Prompt Alert", "CPF_LIKE", "HIGH", "ALERT", "ai_prompt", 25),
        ("CNPJ - AI Prompt Alert", "CNPJ", "HIGH", "ALERT", "ai_prompt", 25),
        ("RG - AI Prompt Alert", "RG_BR", "HIGH", "ALERT", "ai_prompt", 20),
        ("Passport - AI Prompt Alert", "PASSPORT", "HIGH", "ALERT", "ai_prompt", 20),
        ("CNH - AI Prompt Alert", "CNH_BR", "HIGH", "ALERT", "ai_prompt", 20),
        ("CNS - AI Prompt Alert", "CNS_BR", "CRITICAL", "ALERT", "ai_prompt", 15),
        ("Email - AI Prompt Alert", "EMAIL_ADDRESS", "MEDIUM", "ALERT", "ai_prompt", 40),
        ("Phone - AI Prompt Alert", "PHONE_BR", "MEDIUM", "ALERT", "ai_prompt", 40),
        ("Bank Data - AI Prompt Alert", "BANK_ACCOUNT", "HIGH", "ALERT", "ai_prompt", 20),
        ("PIX - AI Prompt Alert", "PIX_KEY", "HIGH", "ALERT", "ai_prompt", 20),
        ("Card Data - AI Prompt Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "ai_prompt", 5),
        ("Card Security Code - AI Prompt Block", "CARD_SECURITY_CODE", "CRITICAL", "BLOCK", "ai_prompt", 1),
        ("Card PIN - AI Prompt Block", "CARD_PIN", "CRITICAL", "BLOCK", "ai_prompt", 1),
        ("Card Track Data - AI Prompt Block", "CARD_TRACK_DATA", "CRITICAL", "BLOCK", "ai_prompt", 1),
        ("Secrets - AI Prompt Block", "SECRET", "CRITICAL", "BLOCK", "ai_prompt", 5),
        ("Credentials - AI Prompt Block", "CREDENTIAL", "CRITICAL", "BLOCK", "ai_prompt", 5),

    ]
    db = SessionLocal()
    try:
        for name, classification, severity, action, channel, priority in defaults:
            if db.query(Policy).filter(Policy.name == name).first():
                continue
            db.add(Policy(
                name=name,
                classification=classification,
                severity=severity,
                action=action,
                enabled=True,
                channel=channel,
                priority=priority,
            ))

        # Upgrade v0.3 policies so existing Community installs actually enforce
        # the channels that were previously alert-only.
        legacy_enforcement = {
            "CPF - Screenshot Protection": ("CRITICAL", "BLOCK", 10),
            "CPF - Removable Media Protection": ("CRITICAL", "BLOCK", 10),
        }
        for legacy_name, (severity, action, priority) in legacy_enforcement.items():
            legacy = db.query(Policy).filter(Policy.name == legacy_name).first()
            if legacy:
                legacy.severity = severity
                legacy.action = action
                legacy.priority = priority
                legacy.enabled = True
        db.commit()
    finally:
        db.close()


seed_default_policies()


class EnrollIn(BaseModel):
    endpoint_id: str = Field(min_length=1, max_length=128)


class HeartbeatIn(BaseModel):
    endpoint_id: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    os: Optional[str] = None
    agent_version: Optional[str] = None
    username: Optional[str] = None


class PolicyIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    classification: str = Field(min_length=1, max_length=128)
    severity: str = "MEDIUM"
    action: str = "AUDIT"
    enabled: bool = True
    channel: str = "filesystem"
    priority: int = 100


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    severity: Optional[str] = None
    action: Optional[str] = None
    enabled: Optional[bool] = None
    channel: Optional[str] = None
    priority: Optional[int] = None


class EventIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    endpoint_id: str = Field(min_length=1, max_length=128)
    hostname: Optional[str] = None
    username: Optional[str] = None
    process: Optional[str] = None
    object_path: Optional[str] = None
    object_hash: Optional[str] = None
    object_size_bytes: int = Field(default=0, ge=0)
    classification: str
    severity: str
    action: str
    masked_value: Optional[str] = None
    fingerprint: Optional[str] = None
    channel: str = "filesystem"
    destination: Optional[str] = None
    policy: Optional[str] = None
    evidence: Optional[str] = None
    blocked: bool = False
    document_type: Optional[str] = None
    detection_count: int = Field(default=1, ge=1, le=10000)
    classification_count: int = Field(default=1, ge=1, le=256)
    context_tags: list[str] = Field(default_factory=list)
    sensitive_filename: bool = False
    destination_trust: Optional[str] = None




class RiskPreviewIn(EventIn):
    pass


class DetectionRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    classification: str = Field(min_length=1, max_length=128)
    pattern: str = Field(min_length=1, max_length=512)
    description: Optional[str] = Field(default=None, max_length=1000)
    enabled: bool = True


class DetectionRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    classification: Optional[str] = Field(default=None, min_length=1, max_length=128)
    pattern: Optional[str] = Field(default=None, min_length=1, max_length=512)
    description: Optional[str] = Field(default=None, max_length=1000)
    enabled: Optional[bool] = None


class AdminSetupIn(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=10, max_length=256)


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class EnrollmentInviteIn(BaseModel):
    label: Optional[str] = Field(default=None, max_length=255)
    ttl_minutes: int = Field(default=30, ge=5, le=1440)
    uses: int = Field(default=1, ge=1, le=100)


ENROLLMENT_KEY_FILE = os.getenv(
    "BSC_DLP_ENROLLMENT_KEY_FILE",
    str(CONFIG_DIR / "enrollment.key"),
)


def hash_agent_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def read_enrollment_key() -> str:
    try:
        return Path(ENROLLMENT_KEY_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )


def admin_count() -> int:
    db = SessionLocal()
    try:
        return db.query(AdminUser).count()
    finally:
        db.close()


def create_admin_session(db, username: str) -> str:
    token = secrets.token_urlsafe(48)
    db.query(AdminSession).filter(AdminSession.username == username).delete()
    db.add(AdminSession(
        username=username,
        token_hash=hash_agent_token(token),
        created_at=now(),
        expires_at=now() + timedelta(hours=SESSION_HOURS),
    ))
    db.commit()
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )


def require_admin(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise HTTPException(status_code=401, detail="admin authentication required")
    token_hash = hash_agent_token(token)
    db = SessionLocal()
    try:
        session = db.query(AdminSession).filter(AdminSession.token_hash == token_hash).first()
        if not session:
            raise HTTPException(status_code=401, detail="invalid admin session")
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now():
            db.delete(session)
            db.commit()
            raise HTTPException(status_code=401, detail="admin session expired")
        return session.username
    finally:
        db.close()


def authenticate_agent(authorization: Optional[str], endpoint_id: Optional[str] = None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, sep, token = authorization.partition(" ")
    if not sep or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_hash = hash_agent_token(token.strip())
    db = SessionLocal()
    try:
        credential = db.query(EndpointCredential).filter(
            EndpointCredential.token_hash == token_hash,
            EndpointCredential.revoked == False,
        ).first()
        if not credential:
            raise HTTPException(
                status_code=401,
                detail="invalid or revoked agent token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if endpoint_id is not None and credential.endpoint_id != endpoint_id:
            raise HTTPException(status_code=403, detail="token does not belong to endpoint")
        return credential.endpoint_id
    finally:
        db.close()


def consume_enrollment_invite(presented: str) -> bool:
    token_hash = hash_agent_token(presented)
    db = SessionLocal()
    try:
        invite = db.query(EnrollmentInvite).filter(
            EnrollmentInvite.token_hash == token_hash,
            EnrollmentInvite.revoked == False,
            EnrollmentInvite.uses_left > 0,
        ).first()
        if not invite:
            return False
        expires = invite.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now():
            return False
        invite.uses_left -= 1
        db.commit()
        return True
    finally:
        db.close()


def risk_for_event(
    body: EventIn,
    recent_count: int,
    recent_object_count: int = 0,
    transfer_object_count: int = 0,
    transfer_bytes: int = 0,
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
        "browser_upload": 26,
        "browser_guard": 28,
        "email": 22,
        "ai": 26,
        "ai_prompt": 26,
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

    if "pii_bundle" in tags:
        score += 8
        reasons.append("privacy:pii_bundle")
    if "pii_profile" in tags:
        score += 10
        reasons.append("privacy:pii_profile")
    if "special_category_linked_identity" in tags:
        score += 18
        reasons.append("privacy:special_category_linked_identity")
    if "pci_account_plus_authentication" in tags:
        score += 20
        reasons.append("pci:account_plus_authentication")

    if "evasive_obfuscation" in tags:
        score += 10
        reasons.append("evasion:strong")
    elif "obfuscated_identifier" in tags:
        score += 5
        reasons.append("evasion:obfuscated")
    if "malformed_identifier" in tags:
        score += 8
        reasons.append("evasion:malformed_identifier")

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

    exfil_channel = channel in {"removable", "browser_upload"}
    if exfil_channel:
        if transfer_object_count >= 100:
            score += 25
            reasons.append("transfer_objects:100+")
        elif transfer_object_count >= 25:
            score += 15
            reasons.append("transfer_objects:25+")
        elif transfer_object_count >= 10:
            score += 8
            reasons.append("transfer_objects:10+")

        mib = 1024 * 1024
        gib = 1024 * mib
        if transfer_bytes >= gib:
            score += 25
            reasons.append("transfer_volume:1GiB+")
        elif transfer_bytes >= 250 * mib:
            score += 18
            reasons.append("transfer_volume:250MiB+")
        elif transfer_bytes >= 50 * mib:
            score += 10
            reasons.append("transfer_volume:50MiB+")
        elif transfer_bytes >= 10 * mib:
            score += 5
            reasons.append("transfer_volume:10MiB+")

    score = min(score, 100)

    if exfil_channel and (transfer_object_count >= 100 or transfer_bytes >= 1024 * 1024 * 1024):
        incident = "MASS_FILE_EXFILTRATION"
    elif exfil_channel and (transfer_object_count >= 25 or transfer_bytes >= 250 * 1024 * 1024):
        incident = "HIGH_VOLUME_FILE_EXFILTRATION"
    elif exfil_channel and (transfer_object_count >= 10 or transfer_bytes >= 50 * 1024 * 1024):
        incident = "BULK_FILE_EXFILTRATION"
    elif channel == "browser_guard" and body.classification.upper() == "BROWSER_GUARD_DISABLED_OR_MISSING":
        incident = "Browser Guard protection disabled or missing"
    elif channel == "browser_guard" and body.classification.upper() == "BROWSER_GUARD_RESTORED":
        incident = "Browser Guard protection restored"
    elif channel == "removable" and detections >= 10:
        incident = "Bulk sensitive-data transfer to removable media"
    elif channel == "removable":
        incident = "Possible removable-media exfiltration"
    elif channel == "browser_upload":
        incident = "Possible sensitive browser upload"
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
    elif channel in {"ai", "ai_prompt"}:
        incident = "Possible Generative AI data exposure"
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

app = FastAPI(
    title="BSC DLP API",
    version="0.6.7",
    description="BSC DLP Community Edition - admin console, risk engine and endpoint enforcement",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icon = APP_ROOT / "dashboard" / "assets" / "bsc-dlp.ico"
    if icon.exists():
        return FileResponse(icon, media_type="image/x-icon")
    return HTMLResponse("", status_code=404)


@app.get("/assets/bsc-dlp-icon.png", include_in_schema=False)
def brand_icon():
    icon = APP_ROOT / "dashboard" / "assets" / "bsc-dlp-icon.png"
    if icon.exists():
        return FileResponse(icon, media_type="image/png")
    return HTMLResponse("", status_code=404)


@app.get("/", include_in_schema=False)
def dashboard():
    index = APP_ROOT / "dashboard" / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("<h1>BSC DLP Community</h1><p>Dashboard asset not found.</p>", status_code=503)


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "engine": "BSC DLP",
        "version": "0.6.7",
        "database": "sqlite",
        "server_time_utc": utc_iso(now()),
        "server_time_local": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


@app.get("/api/v1/auth/status")
def auth_status(request: Request):
    setup_required = admin_count() == 0
    if setup_required:
        return {"setup_required": True, "authenticated": False, "username": None}
    try:
        username = require_admin(request)
        return {"setup_required": False, "authenticated": True, "username": username}
    except HTTPException:
        return {"setup_required": False, "authenticated": False, "username": None}


@app.post("/api/v1/auth/setup")
def auth_setup(body: AdminSetupIn, response: Response):
    db = SessionLocal()
    try:
        if db.query(AdminUser).count() > 0:
            raise HTTPException(status_code=409, detail="administrator already configured")
        username = body.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="username is required")
        salt = os.urandom(16)
        digest = password_digest(body.password, salt)
        db.add(AdminUser(
            username=username,
            password_hash=digest.hex(),
            salt=salt.hex(),
            created_at=now(),
        ))
        db.commit()
        token = create_admin_session(db, username)
        set_session_cookie(response, token)
        return {"status": "created", "username": username}
    finally:
        db.close()


@app.post("/api/v1/auth/login")
def auth_login(body: AdminLoginIn, response: Response):
    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.username == body.username.strip()).first()
        if not user:
            raise HTTPException(status_code=401, detail="invalid credentials")
        candidate = password_digest(body.password, bytes.fromhex(user.salt)).hex()
        if not hmac.compare_digest(candidate, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = create_admin_session(db, user.username)
        set_session_cookie(response, token)
        return {"status": "ok", "username": user.username}
    finally:
        db.close()


@app.post("/api/v1/auth/logout")
def auth_logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        db = SessionLocal()
        try:
            db.query(AdminSession).filter(AdminSession.token_hash == hash_agent_token(token)).delete()
            db.commit()
        finally:
            db.close()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}


@app.post("/api/v1/admin/enrollment-token")
def create_enrollment_invite(body: EnrollmentInviteIn, request: Request):
    require_admin(request)
    token = secrets.token_urlsafe(30)
    expires_at = now() + timedelta(minutes=body.ttl_minutes)
    db = SessionLocal()
    try:
        db.add(EnrollmentInvite(
            label=(body.label or "Endpoint enrollment").strip(),
            token_hash=hash_agent_token(token),
            created_at=now(),
            expires_at=expires_at,
            uses_left=body.uses,
            revoked=False,
        ))
        db.commit()
    finally:
        db.close()
    return {
        "token": token,
        "expires_at": expires_at,
        "uses": body.uses,
        "server": os.getenv("BSC_DLP_PUBLIC_URL", str(request.base_url).rstrip("/")),
    }


@app.post("/api/v1/enroll")
def enroll(body: EnrollIn, x_enrollment_key: Optional[str] = Header(default=None)):
    expected = read_enrollment_key()
    master_ok = bool(expected and x_enrollment_key and secrets.compare_digest(x_enrollment_key, expected))
    invite_ok = False
    if not master_ok and x_enrollment_key:
        invite_ok = consume_enrollment_invite(x_enrollment_key)
    if not (master_ok or invite_ok):
        raise HTTPException(status_code=401, detail="invalid or expired enrollment key")

    db = SessionLocal()
    try:
        existing = db.query(EndpointCredential).filter(
            EndpointCredential.endpoint_id == body.endpoint_id
        ).first()
        token = secrets.token_urlsafe(32)
        if existing:
            existing.token_hash = hash_agent_token(token)
            existing.revoked = False
            existing.created_at = now()
            status = "re_enrolled"
        else:
            db.add(EndpointCredential(
                endpoint_id=body.endpoint_id,
                token_hash=hash_agent_token(token),
                revoked=False,
                created_at=now(),
            ))
            status = "enrolled"
        db.commit()
        return {"status": status, "endpoint_id": body.endpoint_id, "token": token}
    finally:
        db.close()


@app.post("/api/v1/endpoints/heartbeat")
def heartbeat(body: HeartbeatIn, authorization: Optional[str] = Header(default=None)):
    authenticate_agent(authorization, endpoint_id=body.endpoint_id)
    db = SessionLocal()
    try:
        endpoint = db.query(Endpoint).filter(Endpoint.endpoint_id == body.endpoint_id).first()
        if not endpoint:
            endpoint = Endpoint(
                endpoint_id=body.endpoint_id,
                hostname=body.hostname,
                os=body.os,
                agent_version=body.agent_version,
                username=body.username,
                last_seen=now(),
                active=True,
            )
            db.add(endpoint)
        else:
            endpoint.hostname = body.hostname
            endpoint.os = body.os
            endpoint.agent_version = body.agent_version
            endpoint.username = body.username
            endpoint.last_seen = now()
            endpoint.active = True
        db.commit()
        return {"status": "registered", "endpoint_id": body.endpoint_id}
    finally:
        db.close()


@app.get("/api/v1/endpoints")
def endpoints(request: Request):
    require_admin(request)
    cutoff = now() - timedelta(hours=24)
    db = SessionLocal()
    try:
        rows = db.query(Endpoint).order_by(Endpoint.hostname).all()
        result = []
        for row in rows:
            recent = db.query(Event).filter(
                Event.endpoint_id == row.endpoint_id,
                Event.timestamp >= cutoff,
            ).all()
            risk = min(sum(max(int(e.risk_score or 0), 0) for e in recent), 100)
            result.append({
                "endpoint_id": row.endpoint_id,
                "hostname": row.hostname,
                "os": row.os,
                "agent_version": row.agent_version,
                "username": row.username,
                "last_seen": utc_iso(row.last_seen),
                "active": endpoint_is_online(row.last_seen),
                "risk_score": risk,
            })
        return result
    finally:
        db.close()


@app.post("/api/v1/endpoints/{endpoint_id}/revoke")
def revoke_endpoint(endpoint_id: str, request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        cred = db.query(EndpointCredential).filter(EndpointCredential.endpoint_id == endpoint_id).first()
        if not cred:
            raise HTTPException(status_code=404, detail="endpoint credential not found")
        cred.revoked = True
        endpoint = db.query(Endpoint).filter(Endpoint.endpoint_id == endpoint_id).first()
        if endpoint:
            endpoint.active = False
        db.commit()
        return {"status": "revoked", "endpoint_id": endpoint_id}
    finally:
        db.close()


@app.post("/api/v1/policies")
def create_policy(body: PolicyIn, request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        if db.query(Policy).filter(Policy.name == body.name).first():
            raise HTTPException(status_code=409, detail="policy name already exists")
        policy = Policy(
            name=body.name.strip(),
            classification=body.classification.upper(),
            severity=body.severity.upper(),
            action=body.action.upper(),
            enabled=body.enabled,
            channel=body.channel.lower(),
            priority=body.priority,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        return {"status": "created", "id": policy.id, "name": policy.name}
    finally:
        db.close()


@app.get("/api/v1/policies")
def list_policies(request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        rows = db.query(Policy).order_by(Policy.priority.asc(), Policy.id.asc()).all()
        return [{
            "id": r.id,
            "name": r.name,
            "classification": r.classification,
            "severity": r.severity,
            "action": r.action,
            "enabled": r.enabled,
            "channel": r.channel,
            "priority": r.priority,
        } for r in rows]
    finally:
        db.close()


@app.patch("/api/v1/policies/{policy_id}")
def update_policy(policy_id: int, body: PolicyUpdate, request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        policy = db.query(Policy).filter(Policy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="policy not found")
        if body.name is not None:
            policy.name = body.name.strip()
        if body.severity is not None:
            policy.severity = body.severity.upper()
        if body.action is not None:
            policy.action = body.action.upper()
        if body.enabled is not None:
            policy.enabled = body.enabled
        if body.channel is not None:
            policy.channel = body.channel.lower()
        if body.priority is not None:
            policy.priority = body.priority
        db.commit()
        return {"status": "updated", "id": policy.id}
    finally:
        db.close()


@app.get("/api/v1/policies/resolve")
def resolve_policy(
    classification: str,
    channel: str = "filesystem",
    authorization: Optional[str] = Header(default=None),
):
    authenticate_agent(authorization)
    db = SessionLocal()
    try:
        policy = db.query(Policy).filter(
            Policy.enabled == True,
            Policy.classification == classification.upper(),
            Policy.channel == channel.lower(),
        ).order_by(Policy.priority.asc(), Policy.id.asc()).first()
        if not policy:
            return {
                "matched": False,
                "classification": classification.upper(),
                "channel": channel.lower(),
                "action": "AUDIT",
                "severity": "MEDIUM",
                "policy": "Default Audit",
                "priority": 9999,
            }
        return {
            "matched": True,
            "id": policy.id,
            "policy": policy.name,
            "classification": policy.classification,
            "severity": policy.severity,
            "action": policy.action,
            "channel": policy.channel,
            "priority": policy.priority,
        }
    finally:
        db.close()




def validate_detection_pattern(pattern: str) -> str:
    pattern = pattern.strip()
    if not pattern:
        raise HTTPException(status_code=400, detail="pattern is required")
    # Agent uses Go's RE2 regexp engine. Reject constructs RE2 does not support.
    unsupported = ("(?<=", "(?<!", "(?P<", "(?P=", "(?>")
    if any(token in pattern for token in unsupported) or re.search(r"\\[1-9]", pattern):
        raise HTTPException(status_code=400, detail="pattern must be RE2-compatible (no lookbehind/backreferences)")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise HTTPException(status_code=400, detail=f"invalid regex: {exc}")
    return pattern


def serialize_detection_rule(rule: DetectionRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "classification": rule.classification,
        "pattern": rule.pattern,
        "description": rule.description,
        "enabled": bool(rule.enabled),
        "created_at": utc_iso(rule.created_at),
    }


@app.get("/api/v1/detection-rules")
def list_detection_rules(request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        rows = db.query(DetectionRule).order_by(DetectionRule.id.asc()).all()
        return [serialize_detection_rule(r) for r in rows]
    finally:
        db.close()


@app.post("/api/v1/detection-rules")
def create_detection_rule(body: DetectionRuleIn, request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        name = body.name.strip()
        if db.query(DetectionRule).filter(DetectionRule.name == name).first():
            raise HTTPException(status_code=409, detail="detection rule name already exists")
        rule = DetectionRule(
            name=name,
            classification=body.classification.strip().upper(),
            pattern=validate_detection_pattern(body.pattern),
            description=(body.description or "").strip() or None,
            enabled=body.enabled,
            created_at=now(),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return {"status": "created", **serialize_detection_rule(rule)}
    finally:
        db.close()


@app.patch("/api/v1/detection-rules/{rule_id}")
def update_detection_rule(rule_id: int, body: DetectionRuleUpdate, request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        rule = db.query(DetectionRule).filter(DetectionRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="detection rule not found")
        if body.name is not None:
            rule.name = body.name.strip()
        if body.classification is not None:
            rule.classification = body.classification.strip().upper()
        if body.pattern is not None:
            rule.pattern = validate_detection_pattern(body.pattern)
        if body.description is not None:
            rule.description = body.description.strip() or None
        if body.enabled is not None:
            rule.enabled = body.enabled
        db.commit()
        return {"status": "updated", **serialize_detection_rule(rule)}
    finally:
        db.close()


@app.delete("/api/v1/detection-rules/{rule_id}")
def delete_detection_rule(rule_id: int, request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        rule = db.query(DetectionRule).filter(DetectionRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="detection rule not found")
        db.delete(rule)
        db.commit()
        return {"status": "deleted", "id": rule_id}
    finally:
        db.close()


@app.get("/api/v1/agent/detection-rules")
def agent_detection_rules(authorization: Optional[str] = Header(default=None)):
    authenticate_agent(authorization)
    db = SessionLocal()
    try:
        rows = db.query(DetectionRule).filter(DetectionRule.enabled == True).order_by(DetectionRule.id.asc()).all()
        return [{
            "id": r.id,
            "name": r.name,
            "classification": r.classification,
            "pattern": r.pattern,
            "enabled": bool(r.enabled),
        } for r in rows]
    finally:
        db.close()


@app.post("/api/v1/admin/risk-preview")
def risk_preview(body: RiskPreviewIn, request: Request):
    require_admin(request)
    score, incident_type, reasons = risk_for_event(body, 0, 0)
    return {
        "risk_score": score,
        "incident_type": incident_type,
        "risk_reasons": reasons,
        "note": "Preview only. No event was stored and no enforcement action was executed.",
    }


@app.post("/api/v1/events")
def create_event(body: EventIn, authorization: Optional[str] = Header(default=None)):
    authenticate_agent(authorization, endpoint_id=body.endpoint_id)
    db = SessionLocal()
    try:
        if db.query(Event).filter(Event.event_id == body.event_id).first():
            raise HTTPException(status_code=409, detail="event_id already exists")
        event_time = now()
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

        transfer_object_count = 0
        transfer_bytes = 0
        channel = body.channel.lower()
        if channel in {"removable", "browser_upload"}:
            object_sizes: dict[str, int] = {}
            for row in recent_rows:
                if (row.channel or "").lower() != channel:
                    continue
                if body.destination and row.destination and row.destination != body.destination:
                    continue
                key = row.object_hash or row.object_path or row.event_id
                size = max(int(row.object_size_bytes or 0), 0)
                object_sizes[key] = max(object_sizes.get(key, 0), size)

            current_key = body.object_hash or body.object_path or body.event_id
            current_size = max(int(body.object_size_bytes or 0), 0)
            object_sizes[current_key] = max(object_sizes.get(current_key, 0), current_size)
            transfer_object_count = len(object_sizes)
            transfer_bytes = sum(object_sizes.values())

        risk_score, incident_type, risk_reasons = risk_for_event(
            body,
            recent_count,
            recent_object_count,
            transfer_object_count,
            transfer_bytes,
        )
        incident_key = incident_key_for_event(body, incident_type, event_time)
        event = Event(
            event_id=body.event_id,
            timestamp=event_time,
            endpoint_id=body.endpoint_id,
            hostname=body.hostname,
            username=body.username,
            process=body.process,
            object_path=body.object_path,
            object_hash=body.object_hash,
            object_size_bytes=body.object_size_bytes,
            classification=body.classification.upper(),
            severity=body.severity.upper(),
            action=body.action.upper(),
            masked_value=body.masked_value,
            fingerprint=body.fingerprint,
            channel=body.channel.lower(),
            destination=body.destination,
            policy=body.policy,
            evidence=body.evidence,
            blocked=body.blocked,
            risk_score=risk_score,
            incident_type=incident_type,
            incident_key=incident_key,
            document_type=(body.document_type or "").lower() or None,
            detection_count=body.detection_count,
            classification_count=body.classification_count,
            context_tags=json.dumps(body.context_tags[:32], ensure_ascii=False),
            sensitive_filename=body.sensitive_filename,
            destination_trust=(body.destination_trust or "unknown").lower(),
            risk_reasons=json.dumps(risk_reasons, ensure_ascii=False),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return {
            "status": "accepted",
            "id": event.id,
            "event_id": event.event_id,
            "risk_score": risk_score,
            "incident_type": incident_type,
            "incident_key": incident_key,
            "risk_reasons": risk_reasons,
            "transfer_object_count": transfer_object_count,
            "transfer_bytes": transfer_bytes,
        }
    finally:
        db.close()


def _json_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def serialize_event(r: Event) -> dict:
    return {
        "id": r.id,
        "event_id": r.event_id,
        "timestamp": utc_iso(r.timestamp),
        "endpoint_id": r.endpoint_id,
        "hostname": r.hostname,
        "username": r.username,
        "process": r.process,
        "object_path": r.object_path,
        "object_hash": r.object_hash,
        "object_size_bytes": int(r.object_size_bytes or 0),
        "classification": r.classification,
        "severity": r.severity,
        "action": r.action,
        "masked_value": r.masked_value,
        "fingerprint": r.fingerprint,
        "channel": r.channel,
        "destination": r.destination,
        "policy": r.policy,
        "evidence": r.evidence,
        "blocked": r.blocked,
        "risk_score": int(r.risk_score or 0),
        "incident_type": r.incident_type,
        "incident_key": r.incident_key,
        "document_type": r.document_type,
        "detection_count": int(r.detection_count or 1),
        "classification_count": int(r.classification_count or 1),
        "context_tags": _json_list(r.context_tags),
        "sensitive_filename": bool(r.sensitive_filename),
        "destination_trust": r.destination_trust or "unknown",
        "risk_reasons": _json_list(r.risk_reasons),
    }



def _parse_dt(value: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10:
            dt = datetime.fromisoformat(raw)
            if end_of_day:
                dt = dt + timedelta(days=1) - timedelta(microseconds=1)
        else:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid date/time: {value}")


def _event_query(
    db,
    *,
    incident_only: bool = False,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 0,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
):
    query = db.query(Event)
    if incident_only:
        query = query.filter(Event.risk_score >= max(risk_min, 40))
    elif risk_min:
        query = query.filter(Event.risk_score >= risk_min)
    if endpoint:
        term = f"%{endpoint.strip()}%"
        query = query.filter((Event.endpoint_id.ilike(term)) | (Event.hostname.ilike(term)) | (Event.username.ilike(term)))
    if classification:
        query = query.filter(Event.classification == classification.strip().upper())
    if channel:
        query = query.filter(Event.channel == channel.strip().lower())
    if severity:
        query = query.filter(Event.severity == severity.strip().upper())
    if action:
        query = query.filter(Event.action == action.strip().upper())
    if blocked is not None and str(blocked).strip().lower() in {"true", "false", "1", "0", "yes", "no"}:
        value = str(blocked).strip().lower() in {"true", "1", "yes"}
        query = query.filter(Event.blocked == value)
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end, end_of_day=True)
    if start_dt:
        query = query.filter(Event.timestamp >= start_dt)
    if end_dt:
        query = query.filter(Event.timestamp <= end_dt)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            (Event.object_path.ilike(term)) |
            (Event.policy.ilike(term)) |
            (Event.evidence.ilike(term)) |
            (Event.incident_type.ilike(term)) |
            (Event.destination.ilike(term)) |
            (Event.process.ilike(term))
        )
    return query


def _paged_payload(query, page: int, page_size: int, *, incident_only: bool = False) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 25), 10), 100)
    total = query.count()
    pages = max((total + page_size - 1) // page_size, 1)
    if page > pages:
        page = pages
    order = (Event.risk_score.desc(), Event.timestamp.desc()) if incident_only else (Event.timestamp.desc(),)
    rows = query.order_by(*order).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize_event(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@app.get("/api/v1/events/query")
def query_events(
    request: Request,
    page: int = 1,
    page_size: int = 25,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 0,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
):
    require_admin(request)
    db = SessionLocal()
    try:
        query = _event_query(db, endpoint=endpoint, classification=classification, channel=channel,
                             severity=severity, action=action, blocked=blocked, risk_min=max(risk_min, 0),
                             start=start, end=end, q=q)
        return _paged_payload(query, page, page_size)
    finally:
        db.close()


@app.get("/api/v1/incidents/query")
def query_incidents(
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
        query = _event_query(db, incident_only=True, endpoint=endpoint, classification=classification, channel=channel,
                             severity=severity, action=action, blocked=blocked, risk_min=max(risk_min, 40),
                             start=start, end=end, q=q)
        return _paged_payload(query, page, page_size, incident_only=True)
    finally:
        db.close()


@app.get("/api/v1/incidents/correlated")
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
        page_items = items[offset:offset + page_size]
        for item in page_items:
            item["first_seen"] = utc_iso(item["first_seen"])
            item["last_seen"] = utc_iso(item["last_seen"])
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    finally:
        db.close()


def _report_rows(db, *, incident_only: bool = False, **filters):
    return _event_query(db, incident_only=incident_only, **filters).order_by(Event.timestamp.desc()).limit(10000).all()


def _report_metrics(rows: list[Event]) -> dict:
    by_class = {}
    by_channel = {}
    by_action = {}
    endpoints = set()
    blocked = 0
    max_risk = 0
    for row in rows:
        by_class[row.classification or "UNKNOWN"] = by_class.get(row.classification or "UNKNOWN", 0) + 1
        by_channel[row.channel or "unknown"] = by_channel.get(row.channel or "unknown", 0) + 1
        by_action[row.action or "AUDIT"] = by_action.get(row.action or "AUDIT", 0) + 1
        endpoints.add(row.endpoint_id)
        blocked += 1 if row.blocked else 0
        max_risk = max(max_risk, int(row.risk_score or 0))
    return {
        "events": len(rows),
        "incidents": sum(1 for r in rows if int(r.risk_score or 0) >= 40),
        "blocked": blocked,
        "endpoints": len(endpoints),
        "max_risk": max_risk,
        "by_classification": dict(sorted(by_class.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_channel": dict(sorted(by_channel.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_action": dict(sorted(by_action.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


@app.get("/api/v1/reports/summary")
def report_summary(
    request: Request,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 0,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
):
    require_admin(request)
    db = SessionLocal()
    try:
        rows = _report_rows(db, endpoint=endpoint, classification=classification, channel=channel, severity=severity,
                            action=action, blocked=blocked, risk_min=max(risk_min, 0), start=start, end=end, q=q)
        return {"metrics": _report_metrics(rows), "sample": [serialize_event(r) for r in rows[:100]]}
    finally:
        db.close()


def _csv_safe(value) -> str:
    text_value = "" if value is None else str(value)
    if text_value.startswith(("=", "+", "-", "@")):
        return "'" + text_value
    return text_value


def _pdf_text(value, max_len: int = 180) -> str:
    text_value = "" if value is None else str(value)
    text_value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text_value)
    text_value = " ".join(text_value.split())
    if len(text_value) > max_len:
        text_value = text_value[: max_len - 1] + "..."
    return html.escape(text_value, quote=False)


def _report_object_name(path_value) -> str:
    if not path_value:
        return "-"
    normalized = str(path_value).replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or "-"


REPORT_I18N = {
    "pt": {
        "title": "Relatório de Proteção de Dados", "subtitle": "Relatório de Proteção de Dados - Community Edition",
        "subject": "Relatório administrativo de Data Loss Prevention", "period": "Período", "generated": "Gerado em",
        "administrator": "Administrador", "filters": "Filtros", "start": "início", "now": "agora", "no_filters": "Sem filtros adicionais",
        "endpoint": "Endpoint", "classification": "Classificação", "channel": "Canal", "severity": "Severidade", "action": "Ação",
        "blocked": "Bloqueado", "min_risk": "Risco mínimo", "search": "Busca", "events": "Eventos", "incidents": "Incidentes",
        "blocks": "Bloqueios", "endpoints": "Endpoints", "max_risk": "Risco max.", "distribution": "Distribuição",
        "occurrences": "Ocorrências", "no_data": "Sem dados", "date": "Data", "risk": "Risco", "user": "Usuário",
        "blocked_short": "Bloq.", "document": "Documento", "object": "Objeto", "yes": "SIM", "no": "NÃO",
        "no_events": "Nenhum evento para os filtros selecionados.",
        "detail_limit": "O resumo considera {total} eventos. A tabela detalhada foi limitada aos {limit} eventos mais recentes para manter o PDF utilizável.",
        "privacy": "Privacidade: o relatório não inclui valores sensíveis em claro. Dados detectados permanecem mascarados/fingerprinted no BSC DLP.",
        "footer": "BSC DLP Community - Relatório administrativo", "page": "Página", "print": "Imprimir / Salvar como PDF",
        "classifications": "Classificações", "report_heading": "BSC DLP â€” Relatório de Proteção de Dados"
    },
    "en": {
        "title": "Data Protection Report", "subtitle": "Data Protection Report - Community Edition",
        "subject": "Data Loss Prevention administrative report", "period": "Period", "generated": "Generated at",
        "administrator": "Administrator", "filters": "Filters", "start": "start", "now": "now", "no_filters": "No additional filters",
        "endpoint": "Endpoint", "classification": "Classification", "channel": "Channel", "severity": "Severity", "action": "Action",
        "blocked": "Blocked", "min_risk": "Minimum risk", "search": "Search", "events": "Events", "incidents": "Incidents",
        "blocks": "Blocks", "endpoints": "Endpoints", "max_risk": "Max risk", "distribution": "Distribution",
        "occurrences": "Occurrences", "no_data": "No data", "date": "Date", "risk": "Risk", "user": "User",
        "blocked_short": "Blocked", "document": "Document", "object": "Object", "yes": "YES", "no": "NO",
        "no_events": "No events match the selected filters.",
        "detail_limit": "The summary includes {total} events. The detailed table was limited to the {limit} most recent events to keep the PDF usable.",
        "privacy": "Privacy: the report does not include sensitive values in clear text. Detected data remains masked/fingerprinted in BSC DLP.",
        "footer": "BSC DLP Community - Administrative report", "page": "Page", "print": "Print / Save as PDF",
        "classifications": "Classifications", "report_heading": "BSC DLP â€” Data Protection Report"
    },
    "es": {
        "title": "Informe de Protección de Datos", "subtitle": "Informe de Protección de Datos - Community Edition",
        "subject": "Informe administrativo de Data Loss Prevention", "period": "Período", "generated": "Generado el",
        "administrator": "Administrador", "filters": "Filtros", "start": "inicio", "now": "ahora", "no_filters": "Sin filtros adicionales",
        "endpoint": "Endpoint", "classification": "Clasificación", "channel": "Canal", "severity": "Severidad", "action": "Acción",
        "blocked": "Bloqueado", "min_risk": "Riesgo mínimo", "search": "Búsqueda", "events": "Eventos", "incidents": "Incidentes",
        "blocks": "Bloqueos", "endpoints": "Endpoints", "max_risk": "Riesgo máx.", "distribution": "Distribución",
        "occurrences": "Ocurrencias", "no_data": "Sin datos", "date": "Fecha", "risk": "Riesgo", "user": "Usuario",
        "blocked_short": "Bloq.", "document": "Documento", "object": "Objeto", "yes": "SÍ", "no": "NO",
        "no_events": "Ningún evento coincide con los filtros seleccionados.",
        "detail_limit": "El resumen incluye {total} eventos. La tabla detallada se limitó a los {limit} eventos más recientes para mantener el PDF utilizable.",
        "privacy": "Privacidad: el informe no incluye valores sensibles en texto claro. Los datos detectados permanecen enmascarados/fingerprinted en BSC DLP.",
        "footer": "BSC DLP Community - Informe administrativo", "page": "Página", "print": "Imprimir / Guardar como PDF",
        "classifications": "Clasificaciones", "report_heading": "BSC DLP â€” Informe de Protección de Datos"
    },
}


def _report_lang(lang: Optional[str]) -> str:
    value = (lang or "pt").lower().strip()
    return value if value in REPORT_I18N else "pt"


def _report_t(lang: Optional[str], key: str) -> str:
    return REPORT_I18N[_report_lang(lang)].get(key, REPORT_I18N["pt"].get(key, key))


def _report_period_label(start: Optional[str], end: Optional[str], lang: str = "pt") -> str:
    def compact(value: Optional[str], fallback: str) -> str:
        if not value:
            return fallback
        return str(value).replace("T", " ").replace("Z", "")[:19]

    return f"{compact(start, _report_t(lang, 'start'))} â€” {compact(end, _report_t(lang, 'now'))}"


def _report_filter_text(lang: str = "pt", **filters) -> str:
    labels = {
        "endpoint": _report_t(lang, "endpoint"),
        "classification": _report_t(lang, "classification"),
        "channel": _report_t(lang, "channel"),
        "severity": _report_t(lang, "severity"),
        "action": _report_t(lang, "action"),
        "blocked": _report_t(lang, "blocked"),
        "risk_min": _report_t(lang, "min_risk"),
        "q": _report_t(lang, "search"),
    }
    parts = []
    for key, label in labels.items():
        value = filters.get(key)
        if value in (None, "", 0, "0"):
            continue
        parts.append(f"{label}: {value}")
    return " | ".join(parts) if parts else _report_t(lang, "no_filters")


def _build_report_pdf(*, rows: list[Event], metrics: dict, admin: str, start: Optional[str], end: Optional[str], lang: str = "pt", **filters) -> bytes:
    lang = _report_lang(lang)
    rt = lambda key: _report_t(lang, key)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f"BSC DLP - {rt('title')}",
        author="BSC DLP Community",
        subject=rt("subject"),
    )

    pink = colors.HexColor("#FF2D95")
    pink_soft = colors.HexColor("#FFE4F2")
    ink = colors.HexColor("#130A11")
    muted = colors.HexColor("#675965")
    line = colors.HexColor("#E7D8E2")
    surface = colors.HexColor("#F9F4F7")
    success = colors.HexColor("#1C7C54")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BSCReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=23,
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    subtitle_style = ParagraphStyle(
        "BSCReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#E6CEDB"),
    )
    section_style = ParagraphStyle(
        "BSCSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=ink,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body_style = ParagraphStyle(
        "BSCBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=muted,
    )
    cell_style = ParagraphStyle(
        "BSCCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=6.6,
        leading=8,
        textColor=ink,
    )
    cell_bold_style = ParagraphStyle(
        "BSCCellBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    header_cell_style = ParagraphStyle(
        "BSCHeaderCell",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    story = []
    logo_path = APP_ROOT / "dashboard" / "assets" / "bsc-dlp-icon.png"
    header_text = [
        Paragraph("BSC DLP", title_style),
        Paragraph(rt("subtitle"), subtitle_style),
    ]
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=18 * mm, height=18 * mm)
    else:
        logo = Paragraph("BSC", ParagraphStyle("LogoFallback", parent=title_style, fontSize=14))
    header = Table([[logo, header_text]], colWidths=[22 * mm, 240 * mm], hAlign="LEFT")
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ink),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BOX", (0, 0), (-1, -1), 0.8, pink),
    ]))
    story.extend([header, Spacer(1, 4 * mm)])

    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    info = Table([
        [Paragraph(rt("period"), cell_bold_style), Paragraph(_pdf_text(_report_period_label(start, end, lang)), body_style),
         Paragraph(rt("generated"), cell_bold_style), Paragraph(_pdf_text(generated_at), body_style),
         Paragraph(rt("administrator"), cell_bold_style), Paragraph(_pdf_text(admin, 80), body_style)],
        [Paragraph(rt("filters"), cell_bold_style), Paragraph(_pdf_text(_report_filter_text(lang=lang, **filters), 420), body_style), "", "", "", ""],
    ], colWidths=[18*mm, 67*mm, 18*mm, 54*mm, 24*mm, 73*mm])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), surface),
        ("BOX", (0,0), (-1,-1), 0.4, line),
        ("INNERGRID", (0,0), (-1,-1), 0.25, line),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("SPAN", (1,1), (-1,1)),
    ]))
    story.append(info)
    story.append(Spacer(1, 4 * mm))

    cards = [
        (rt("events"), metrics.get("events", 0)),
        (rt("incidents"), metrics.get("incidents", 0)),
        (rt("blocks"), metrics.get("blocked", 0)),
        (rt("endpoints"), metrics.get("endpoints", 0)),
        (rt("max_risk"), metrics.get("max_risk", 0)),
    ]
    card_data = [[Paragraph(_pdf_text(label), body_style) for label, _ in cards],
                 [Paragraph(f"<b>{int(value or 0)}</b>", ParagraphStyle("CardValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=19, leading=21, textColor=ink)) for _, value in cards]]
    card_table = Table(card_data, colWidths=[51*mm]*5)
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ("BOX", (0,0), (-1,-1), 0.5, line),
        ("INNERGRID", (0,0), (-1,-1), 0.5, line),
        ("TOPPADDING", (0,0), (-1,0), 7),
        ("BOTTOMPADDING", (0,0), (-1,0), 1),
        ("TOPPADDING", (0,1), (-1,1), 1),
        ("BOTTOMPADDING", (0,1), (-1,1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("LINEABOVE", (0,0), (-1,0), 2, pink),
    ]))
    story.append(card_table)

    def top_table(title: str, values: dict, max_items: int = 10):
        data = [[Paragraph(title, cell_bold_style), Paragraph(rt("occurrences"), cell_bold_style)]]
        items = list(values.items())[:max_items]
        if not items:
            items = [(rt("no_data"), 0)]
        for key, value in items:
            data.append([Paragraph(_pdf_text(key, 100), cell_style), Paragraph(str(int(value)), cell_style)])
        table = Table(data, colWidths=[61*mm, 19*mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), pink_soft),
            ("TEXTCOLOR", (0,0), (-1,0), ink),
            ("BOX", (0,0), (-1,-1), 0.4, line),
            ("INNERGRID", (0,0), (-1,-1), 0.25, line),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        return table

    story.append(Paragraph(rt("distribution"), section_style))
    distributions = Table([[top_table(rt("classification"), metrics.get("by_classification", {})),
                            top_table(rt("channel"), metrics.get("by_channel", {})),
                            top_table(rt("action"), metrics.get("by_action", {}))]],
                          colWidths=[84*mm, 84*mm, 84*mm])
    distributions.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 3)]))
    story.append(distributions)

    story.append(Paragraph(rt("events"), section_style))
    detail_limit = 2000
    detail_rows = rows[:detail_limit]
    event_data = [[
        Paragraph(rt("date"), header_cell_style),
        Paragraph(rt("risk"), header_cell_style),
        Paragraph(rt("endpoint"), header_cell_style),
        Paragraph(rt("user"), header_cell_style),
        Paragraph(rt("classification"), header_cell_style),
        Paragraph(rt("channel"), header_cell_style),
        Paragraph(rt("action"), header_cell_style),
        Paragraph(rt("blocked_short"), header_cell_style),
        Paragraph(rt("document"), header_cell_style),
        Paragraph(rt("object"), header_cell_style),
    ]]
    for row in detail_rows:
        timestamp = host_iso(row.timestamp) or ""
        event_data.append([
            Paragraph(_pdf_text(timestamp, 32), cell_style),
            Paragraph(str(int(row.risk_score or 0)), cell_style),
            Paragraph(_pdf_text(row.hostname or row.endpoint_id, 45), cell_style),
            Paragraph(_pdf_text(row.username or "-", 35), cell_style),
            Paragraph(_pdf_text(row.classification or "-", 36), cell_style),
            Paragraph(_pdf_text(row.channel or "-", 20), cell_style),
            Paragraph(_pdf_text(row.action or "AUDIT", 20), cell_style),
            Paragraph(rt("yes") if row.blocked else rt("no"), cell_style),
            Paragraph(_pdf_text((row.document_type or "-").upper(), 16), cell_style),
            Paragraph(_pdf_text(_report_object_name(row.object_path), 65), cell_style),
        ])
    if not detail_rows:
        event_data.append([Paragraph(rt("no_events"), cell_style)] + [""] * 9)

    event_table = Table(
        event_data,
        repeatRows=1,
        colWidths=[28*mm, 12*mm, 32*mm, 27*mm, 31*mm, 21*mm, 21*mm, 13*mm, 20*mm, 50*mm],
    )
    event_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), ink),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BOX", (0,0), (-1,-1), 0.35, line),
        ("INNERGRID", (0,0), (-1,-1), 0.2, line),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, surface]),
        ("SPAN", (0,1), (-1,1)) if not detail_rows else ("LINEBELOW", (0,0), (-1,0), 1, pink),
    ]))
    story.append(event_table)
    if len(rows) > detail_limit:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            rt("detail_limit").format(total=len(rows), limit=detail_limit),
            body_style,
        ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        rt("privacy"),
        ParagraphStyle("Privacy", parent=body_style, textColor=success, fontName="Helvetica-Bold"),
    ))

    def decorate_page(canvas, doc):
        canvas.saveState()
        page_width, _ = landscape(A4)
        canvas.setStrokeColor(pink)
        canvas.setLineWidth(1.1)
        canvas.line(12 * mm, 10 * mm, page_width - 12 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(12 * mm, 6.3 * mm, rt("footer"))
        canvas.drawRightString(page_width - 12 * mm, 6.3 * mm, f"{rt('page')} {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return buffer.getvalue()


@app.get("/api/v1/reports/export.csv")
def report_csv(
    request: Request,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 0,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
    lang: str = "pt",
):
    require_admin(request)
    lang = _report_lang(lang)
    db = SessionLocal()
    try:
        rows = _report_rows(db, endpoint=endpoint, classification=classification, channel=channel, severity=severity,
                            action=action, blocked=blocked, risk_min=max(risk_min, 0), start=start, end=end, q=q)
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow([_report_t(lang, "date"), _report_t(lang, "risk"), "endpoint_id", "hostname", _report_t(lang, "user"), _report_t(lang, "classification"), _report_t(lang, "channel"), _report_t(lang, "severity"),
                         _report_t(lang, "action"), _report_t(lang, "blocked"), _report_t(lang, "document"), _report_t(lang, "object"), "policy", "masked_value", "evidence"])
        for r in rows:
            writer.writerow([
                host_iso(r.timestamp) or "", int(r.risk_score or 0), _csv_safe(r.endpoint_id), _csv_safe(r.hostname),
                _csv_safe(r.username), _csv_safe(r.classification), _csv_safe(r.channel), _csv_safe(r.severity), _csv_safe(r.action),
                _report_t(lang, "yes") if r.blocked else _report_t(lang, "no"), _csv_safe(r.document_type), _csv_safe(r.object_path), _csv_safe(r.policy),
                _csv_safe(r.masked_value), _csv_safe(r.evidence),
            ])
        stamp = now().strftime("%Y%m%d-%H%M%S")
        return Response(content="\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="bsc-dlp-report-{stamp}.csv"'})
    finally:
        db.close()


@app.get("/api/v1/reports/export.pdf")
def report_pdf(
    request: Request,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 0,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
    lang: str = "pt",
):
    admin = require_admin(request)
    lang = _report_lang(lang)
    db = SessionLocal()
    try:
        rows = _report_rows(
            db,
            endpoint=endpoint,
            classification=classification,
            channel=channel,
            severity=severity,
            action=action,
            blocked=blocked,
            risk_min=max(risk_min, 0),
            start=start,
            end=end,
            q=q,
        )
        metrics = _report_metrics(rows)
        pdf_bytes = _build_report_pdf(
            rows=rows,
            metrics=metrics,
            admin=admin,
            start=start,
            end=end,
            endpoint=endpoint,
            classification=classification,
            channel=channel,
            severity=severity,
            action=action,
            blocked=blocked,
            risk_min=max(risk_min, 0),
            q=q,
            lang=lang,
        )
        stamp = now().strftime("%Y%m%d-%H%M%S")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="bsc-dlp-report-{stamp}.pdf"',
                "Cache-Control": "no-store",
            },
        )
    finally:
        db.close()


@app.get("/api/v1/reports/print")
def report_print(
    request: Request,
    endpoint: Optional[str] = None,
    classification: Optional[str] = None,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
    action: Optional[str] = None,
    blocked: Optional[str] = None,
    risk_min: int = 0,
    start: Optional[str] = None,
    end: Optional[str] = None,
    q: Optional[str] = None,
    lang: str = "pt",
):
    admin = require_admin(request)
    lang = _report_lang(lang)
    db = SessionLocal()
    try:
        rows = _report_rows(db, endpoint=endpoint, classification=classification, channel=channel, severity=severity,
                            action=action, blocked=blocked, risk_min=max(risk_min, 0), start=start, end=end, q=q)
        metrics = _report_metrics(rows)
        period = html.escape(_report_period_label(start, end, lang))
        table_row_parts = []
        for r in rows[:1000]:
            object_name = "-"
            if r.object_path:
                normalized_path = str(r.object_path).replace("\\", "/")
                object_name = normalized_path.rsplit("/", 1)[-1]
            table_row_parts.append(
                "<tr>"
                f"<td>{html.escape(r.timestamp.isoformat() if r.timestamp else '')}</td>"
                f"<td>{int(r.risk_score or 0)}</td>"
                f"<td>{html.escape(r.hostname or r.endpoint_id)}</td>"
                f"<td>{html.escape(r.classification or '')}</td>"
                f"<td>{html.escape(r.channel or '')}</td>"
                f"<td>{html.escape(r.action or '')}</td>"
                f"<td>{html.escape(_report_t(lang, 'yes') if r.blocked else _report_t(lang, 'no'))}</td>"
                f"<td>{html.escape(object_name)}</td>"
                "</tr>"
            )
        table_rows = "".join(table_row_parts)
        top_classes = "".join(f"<li><strong>{html.escape(k)}</strong>: {v}</li>" for k, v in list(metrics['by_classification'].items())[:10]) or f"<li>{html.escape(_report_t(lang, 'no_events'))}</li>"
        doc = f"""<!doctype html><html lang="{'pt-BR' if lang=='pt' else 'en' if lang=='en' else 'es'}"><head><meta charset="utf-8"><title>BSC DLP Report</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;color:#171217;margin:34px}}h1{{margin:0;color:#d41472}}.meta{{color:#665b63;margin:6px 0 22px}}.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:18px 0}}.card{{border:1px solid #ddd;padding:12px;border-radius:8px}}.card strong{{display:block;font-size:24px}}table{{border-collapse:collapse;width:100%;font-size:10px}}th,td{{border-bottom:1px solid #ddd;padding:7px;text-align:left}}th{{background:#f7edf3}}ul{{columns:2}}@media print{{button{{display:none}}body{{margin:12mm}}}}</style></head><body>
<button onclick="window.print()">{html.escape(_report_t(lang, "print"))}</button><h1>{html.escape(_report_t(lang, "report_heading"))}</h1><div class="meta">{html.escape(_report_t(lang, "period"))}: {period} · {html.escape(_report_t(lang, "generated"))}: {now().isoformat()} · {html.escape(_report_t(lang, "administrator"))}: {html.escape(admin)}</div>
<div class="cards"><div class="card">{html.escape(_report_t(lang, "events"))}<strong>{metrics['events']}</strong></div><div class="card">{html.escape(_report_t(lang, "incidents"))}<strong>{metrics['incidents']}</strong></div><div class="card">{html.escape(_report_t(lang, "blocks"))}<strong>{metrics['blocked']}</strong></div><div class="card">{html.escape(_report_t(lang, "endpoints"))}<strong>{metrics['endpoints']}</strong></div><div class="card">{html.escape(_report_t(lang, "max_risk"))}<strong>{metrics['max_risk']}</strong></div></div>
<h2>{html.escape(_report_t(lang, "classifications"))}</h2><ul>{top_classes}</ul><h2>{html.escape(_report_t(lang, "events"))}</h2><table><thead><tr><th>{html.escape(_report_t(lang, "date"))}</th><th>{html.escape(_report_t(lang, "risk"))}</th><th>Endpoint</th><th>{html.escape(_report_t(lang, "classification"))}</th><th>{html.escape(_report_t(lang, "channel"))}</th><th>{html.escape(_report_t(lang, "action"))}</th><th>{html.escape(_report_t(lang, "blocked_short"))}</th><th>{html.escape(_report_t(lang, "object"))}</th></tr></thead><tbody>{table_rows}</tbody></table></body></html>"""
        return HTMLResponse(doc)
    finally:
        db.close()


@app.get("/api/v1/events")
def list_events(request: Request, limit: int = 100):
    require_admin(request)
    limit = min(max(limit, 1), 1000)
    db = SessionLocal()
    try:
        rows = db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()
        return [serialize_event(r) for r in rows]
    finally:
        db.close()


@app.get("/api/v1/incidents")
def incidents(request: Request, limit: int = 100):
    require_admin(request)
    limit = min(max(limit, 1), 500)
    db = SessionLocal()
    try:
        rows = db.query(Event).filter(Event.risk_score >= 40).order_by(
            Event.risk_score.desc(), Event.timestamp.desc()
        ).limit(limit).all()
        return [serialize_event(r) for r in rows]
    finally:
        db.close()


@app.get("/api/v1/stats")
def stats(request: Request):
    require_admin(request)
    db = SessionLocal()
    try:
        total_events = db.query(Event).count()
        endpoint_rows = db.query(Endpoint).all()
        endpoints_online = sum(1 for e in endpoint_rows if endpoint_is_online(e.last_seen))
        blocked = db.query(Event).filter(Event.blocked == True).count()
        incidents_count = db.query(Event).filter(Event.risk_score >= 40).count()
        classifications = {x[0] for x in db.query(Event.classification).all() if x[0]}
        latest = db.query(Event).order_by(Event.timestamp.desc()).limit(200).all()
        max_risk = max([int(e.risk_score or 0) for e in latest] or [0])
        return {
            "events": total_events,
            "endpoints": endpoints_online,
            "endpoints_total": len(endpoint_rows),
            "blocked": blocked,
            "incidents": incidents_count,
            "classification_types": len(classifications),
            "risk_score": max_risk,
        }
    finally:
        db.close()


@app.get("/api/v1/capabilities")
def capabilities(request: Request):
    require_admin(request)
    return {
        "documents": ["PDF", "DOCX", "XLSX", "PPTX", "TXT", "CSV", "JSON", "XML", "LOG", "MD"],
        "ocr": ["PNG", "JPG", "JPEG", "TIFF", "BMP", "WEBP", "scanned PDF (when Tesseract + pdftoppm are available)"],
        "channels": ["filesystem", "download", "screenshot", "removable", "messaging"],
        "channel_status": {
            "active": ["filesystem", "download", "screenshot", "removable"],
            "active_windows": ["messaging"],
            "foundation": ["clipboard", "email", "ai"],
        },
        "screenshot_clipboard_sensor": {
            "capture_active_windows": True,
            "capture_mode": "clipboard_image_ocr_cf_bitmap_normalized",
            "formats": ["CF_BITMAP", "CF_DIBV5", "CF_DIB"],
            "raw_image_persisted": False,
            "temporary_bmp_deleted_after_ocr": True,
            "clipboard_clear_on_block": True,
            "pre_capture_prevention": False,
            "note": "Windows clipboard screenshots (including Win+Shift+S when an image reaches the clipboard) are OCR-inspected locally. BLOCK clears the clipboard after detection; it does not prevent the pixels from being captured in the first place.",
        },
        "browser_sensor": {
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
        "messaging_sensor": {
            "capture_active_windows": True,
            "capture_mode": "clipboard_foreground_target",
            "providers": ["whatsapp", "teams", "slack", "telegram", "discord"],
            "raw_clipboard_stored": False,
            "clipboard_block_supported": True,
            "web_capture_active": False,
            "file_upload_capture_active": False,
            "note": "Windows desktop messaging protection observes sensitive clipboard exposure to recognized foreground messaging apps. It does not read chat messages or decrypt traffic.",
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
        "anti_evasion": {
            "separator_normalization": True,
            "zero_width_detection": True,
            "unicode_digits": True,
            "number_words": ["pt", "en", "es"],
            "validated_checksums": ["CPF", "CNPJ", "CREDIT_CARD"],
            "malformed_cpf_context": True,
            "whole_document_digit_collapse": False,
        },
        "optional_custom_examples": ["CEP_BR", "PHONE_BR"],
        "classifiers": [
            "CPF", "CPF_LIKE", "CNPJ", "CREDIT_CARD", "EMAIL_ADDRESS", "RG_BR",
            "PIX_KEY", "BANK_ACCOUNT", "PASSPORT", "CREDENTIAL", "SECRET"
        ],
        "enforcement": {
            "endpoint_quarantine": True,
            "pre_write_minifilter": False,
            "note": "BLOCK removes the detected object from its source path into endpoint quarantine after write detection. Kernel pre-write blocking requires the future Windows minifilter module.",
        },
    }

