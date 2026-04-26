"""
Website Blocker System
Admin defines blocked domains → agent enforces them → violations logged as anomalies.

This is rule-based, no ML. Agent checks active window title + app name against blocklist.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, select

from app.db.session import get_db
from app.models import AnomalyLog, AnomalyType, Department, Device, DeviceStatus, Employee
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.logging import get_logger
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.audit import log_admin_action
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/blocker", tags=["website-blocker"])
log = get_logger("blocker")


def _metadata_text(field_name: str):
    expr = AnomalyLog.event_metadata[field_name]
    if hasattr(expr, "as_string"):
        return expr.as_string()
    if hasattr(expr, "astext"):
        return expr.astext
    return expr.cast(String)


def _normalize_domain(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = normalized.replace("https://", "").replace("http://", "").replace("www.", "")
    return normalized.split("/", 1)[0]


def _domain_matches(rule_domain: str, reported_domain: str) -> bool:
    rule = _normalize_domain(rule_domain)
    reported = _normalize_domain(reported_domain)
    return reported == rule or reported.endswith(f".{rule}") or rule in reported


def _find_block_rule(domain: str) -> Optional[dict]:
    for entry in _blocked_domains.values():
        if _domain_matches(entry.get("domain", ""), domain):
            return entry
    return None


def _metadata_domains(metadata: Optional[dict[str, Any]]) -> list[str]:
    if not metadata:
        return []

    domains: list[str] = []
    raw_domains = metadata.get("blocked_domains")
    if isinstance(raw_domains, list):
        domains.extend(str(domain) for domain in raw_domains if domain)
    elif isinstance(raw_domains, str) and raw_domains.strip():
        domains.append(raw_domains)

    single_domain = metadata.get("domain")
    if isinstance(single_domain, str) and single_domain.strip():
        domains.append(single_domain)

    domain_details = metadata.get("domain_details")
    if isinstance(domain_details, dict):
        domains.extend(str(domain) for domain in domain_details.keys() if domain)

    seen: set[str] = set()
    out: list[str] = []
    for domain in domains:
        normalized = _normalize_domain(domain)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def _domain_detail(metadata: dict[str, Any], domain: str) -> dict[str, Any]:
    details = metadata.get("domain_details")
    if isinstance(details, dict):
        value = details.get(domain) or details.get(_normalize_domain(domain))
        if isinstance(value, dict):
            return value
    return {}


def _serialize_violation(
    anomaly: AnomalyLog,
    employee_name: Optional[str],
    employee_email: Optional[str],
    department_name: Optional[str],
    hostname: Optional[str],
) -> dict[str, Any]:
    metadata = anomaly.event_metadata or {}
    domains = _metadata_domains(metadata)
    primary_domain = domains[0] if domains else None
    primary_detail = _domain_detail(metadata, primary_domain or "")
    apps = primary_detail.get("apps") if isinstance(primary_detail.get("apps"), list) else None

    return {
        "id": str(anomaly.id),
        "employee_id": str(anomaly.employee_id),
        "employee_name": employee_name,
        "employee_email": employee_email,
        "department_name": department_name,
        "device_id": str(anomaly.device_id),
        "hostname": hostname,
        "domain": primary_domain,
        "domains": domains,
        "app_name": metadata.get("app_name") or (apps[0] if apps else None),
        "window_title": metadata.get("window_title"),
        "category": primary_detail.get("category") or metadata.get("category"),
        "severity": metadata.get("severity_override") or metadata.get("severity") or primary_detail.get("severity") or "medium",
        "detected_at": anomaly.detected_at.isoformat(),
        "description": anomaly.description,
        "is_reviewed": anomaly.is_reviewed,
        "metadata": metadata,
    }


async def _blocked_violation_rows(
    db: AsyncSession,
    *,
    days: int,
    employee_id: Optional[uuid.UUID] = None,
    limit: int = 500,
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        select(
            AnomalyLog,
            Employee.full_name.label("employee_name"),
            Employee.email.label("employee_email"),
            Department.name.label("department_name"),
            Device.hostname.label("hostname"),
        )
        .outerjoin(Employee, AnomalyLog.employee_id == Employee.id)
        .outerjoin(Department, Employee.department_id == Department.id)
        .outerjoin(Device, AnomalyLog.device_id == Device.id)
        .where(
            AnomalyLog.detected_at >= since,
            _metadata_text("violation_type") == "blocked_domain",
        )
        .order_by(AnomalyLog.detected_at.desc())
        .limit(limit)
    )
    if employee_id:
        query = query.where(AnomalyLog.employee_id == employee_id)

    result = await db.execute(query)
    return result.all()


# ─── Models ──────────────────────────────────────────────────────────────────

class BlockedDomain(BaseModel):
    id: Optional[str] = None
    domain: str
    reason: str
    category: str = "general"  # social, adult, gaming, streaming, illegal, custom
    severity: str = "medium"   # low, medium, high
    applies_to_all: bool = True
    department_id: Optional[str] = None
    employee_id: Optional[str] = None
    created_at: Optional[str] = None
    is_active: bool = True

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        normalized = normalized.replace("https://", "").replace("http://", "").replace("www.", "")
        normalized = normalized.split("/", 1)[0]
        if not normalized or "." not in normalized:
            raise ValueError("Invalid domain")
        return normalized


class BlockViolation(BaseModel):
    device_token: str
    domain: str
    window_title: str
    app_name: str
    timestamp: str
    current_url: Optional[str] = None


# ─── In-memory store (use DB table in production) ─────────────────────────────

_blocked_domains: dict[str, dict] = {}

# Pre-loaded default blocks for common distractions
DEFAULT_BLOCKS = [
    {"domain": "facebook.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "instagram.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "twitter.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "tiktok.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "reddit.com", "reason": "Social media / forums", "category": "social", "severity": "low"},
    {"domain": "youtube.com", "reason": "Video streaming", "category": "streaming", "severity": "medium"},
    {"domain": "netflix.com", "reason": "Video streaming", "category": "streaming", "severity": "high"},
    {"domain": "twitch.tv", "reason": "Gaming / streaming", "category": "gaming", "severity": "high"},
    {"domain": "steam.com", "reason": "Gaming platform", "category": "gaming", "severity": "high"},
]

# Auto-load defaults on startup so the blocklist is never empty
def _auto_load_defaults():
    for block in DEFAULT_BLOCKS:
        domain_id = str(uuid.uuid4())
        _blocked_domains[domain_id] = {
            "id": domain_id,
            "domain": block["domain"],
            "reason": block["reason"],
            "category": block["category"],
            "severity": block["severity"],
            "applies_to_all": True,
            "department_id": None,
            "employee_id": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "violation_count": 0,
        }

_auto_load_defaults()
log.info(f"blocker_defaults_loaded: {len(_blocked_domains)} domains")



# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/domains", response_model=List[dict])
async def list_blocked_domains(admin=Depends(require_admin_read)):
    """List all blocked domains."""
    return list(_blocked_domains.values())


@router.post("/domains", status_code=201)
async def add_blocked_domain(
    payload: BlockedDomain,
    admin=Depends(require_admin_write),
):
    domain_id = str(uuid.uuid4())
    domain = payload.domain

    _blocked_domains[domain_id] = {
        "id": domain_id,
        "domain": domain,
        "reason": payload.reason,
        "category": payload.category,
        "severity": payload.severity,
        "applies_to_all": payload.applies_to_all,
        "department_id": payload.department_id,
        "employee_id": payload.employee_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "violation_count": 0,
    }
    log.info("domain_blocked", domain=domain, by=str(admin.id))
    log_admin_action("domain_blocked", admin_id=str(admin.id), domain=domain)
    return _blocked_domains[domain_id]


@router.delete("/domains/{domain_id}", status_code=204)
async def remove_blocked_domain(domain_id: str, admin=Depends(require_admin_write)):
    if domain_id not in _blocked_domains:
        raise HTTPException(status_code=404, detail="Domain not found")
    del _blocked_domains[domain_id]
    log_admin_action("domain_removed", admin_id=str(admin.id), domain_id=domain_id)


@router.patch("/domains/{domain_id}/toggle")
async def toggle_domain(domain_id: str, admin=Depends(require_admin_write)):
    if domain_id not in _blocked_domains:
        raise HTTPException(status_code=404, detail="Domain not found")
    _blocked_domains[domain_id]["is_active"] = not _blocked_domains[domain_id]["is_active"]
    log_admin_action("domain_toggled", admin_id=str(admin.id), domain_id=domain_id)
    return _blocked_domains[domain_id]


@router.post("/load-defaults", status_code=201)
async def load_default_blocks(admin=Depends(require_admin_write)):
    """Load the default block list (common distractions)."""
    added = 0
    existing_domains = {v["domain"] for v in _blocked_domains.values()}
    for block in DEFAULT_BLOCKS:
        domain = block["domain"]
        if domain not in existing_domains:
            domain_id = str(uuid.uuid4())
            _blocked_domains[domain_id] = {
                "id": domain_id,
                "domain": domain,
                "reason": block["reason"],
                "category": block["category"],
                "severity": block["severity"],
                "applies_to_all": True,
                "department_id": None,
                "employee_id": None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "violation_count": 0,
            }
            added += 1
    log_admin_action("domain_defaults_loaded", admin_id=str(admin.id), added=added)
    return {"added": added, "message": f"Loaded {added} default blocks"}


@router.get("/domains/active-list")
async def get_active_blocklist(
    request: Request,
    device_token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by agent every 5 minutes to sync its local blocklist.
    No auth required — device token validated separately.
    Returns just the domain strings for efficient matching.
    """
    resolved_token = (device_token or request.headers.get("x-device-token") or "").strip()
    if not resolved_token:
        raise HTTPException(status_code=401, detail="Device token required")

    enforce_rate_limit(
        request,
        key_prefix="blocklist_sync",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=resolved_token,
    )

    result = await db.execute(
        select(Device).where(
            Device.device_token == resolved_token,
            Device.status == DeviceStatus.approved,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device")

    active = [v["domain"] for v in _blocked_domains.values() if v["is_active"]]
    return {"domains": active, "count": len(active)}


@router.post("/violation")
async def report_violation(payload: BlockViolation, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Agent reports when a blocked domain is accessed.
    Creates an anomaly log entry and broadcasts to dashboard.
    """
    enforce_rate_limit(
        request,
        key_prefix="blocker_violation",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=payload.device_token,
    )

    # Validate device
    result = await db.execute(
        select(Device).where(
            Device.device_token == payload.device_token,
            Device.status == DeviceStatus.approved,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device")

    employee_result = await db.execute(
        select(Employee, Department.name.label("department_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.id == device.employee_id)
    )
    employee_row = employee_result.one_or_none()
    employee = employee_row[0] if employee_row else None
    department_name = employee_row[1] if employee_row else None

    reported_domain = _normalize_domain(payload.domain)
    matched_rule = _find_block_rule(reported_domain)
    if matched_rule:
        matched_rule["violation_count"] = int(matched_rule.get("violation_count", 0) or 0) + 1

    severity = (matched_rule or {}).get("severity", "high")
    category = (matched_rule or {}).get("category")

    try:
        detected_at = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=timezone.utc)
    except ValueError:
        detected_at = datetime.now(timezone.utc)

    duplicate_since = detected_at - timedelta(hours=1)
    duplicate_result = await db.execute(
        select(AnomalyLog)
        .where(
            AnomalyLog.employee_id == device.employee_id,
            AnomalyLog.device_id == device.id,
            AnomalyLog.anomaly_type == AnomalyType.unusual_app_usage,
            AnomalyLog.detected_at >= duplicate_since,
            _metadata_text("violation_type") == "blocked_domain",
            _metadata_text("domain") == reported_domain,
        )
        .order_by(AnomalyLog.detected_at.desc())
        .limit(1)
    )
    existing_anomaly = duplicate_result.scalar_one_or_none()
    if existing_anomaly:
        return {
            "status": "duplicate_ignored",
            "screenshot_requested": False,
            "trigger": "violation",
            "anomaly_id": str(existing_anomaly.id),
            "employee_id": str(device.employee_id),
            "employee_name": employee.full_name if employee else None,
            "domain": reported_domain,
        }

    current_url = (payload.current_url or "").strip()
    employee_name = employee.full_name if employee else "Unknown employee"
    description = f"{employee_name} accessed blocked site: {reported_domain}"
    if payload.app_name:
        description += f" via {payload.app_name}"
    if current_url:
        description += f". URL: {current_url}"
    elif payload.window_title:
        description += f". Window: '{payload.window_title}'"

    anomaly = AnomalyLog(
        employee_id=device.employee_id,
        device_id=device.id,
        anomaly_type=AnomalyType.unusual_app_usage,
        detected_at=detected_at,
        description=description,
        event_metadata={
            "domain": reported_domain,
            "blocked_domains": [reported_domain],
            "app_name": payload.app_name,
            "window_title": payload.window_title,
            "current_url": current_url or None,
            "violation_type": "blocked_domain",
            "violation_count": 1,
            "severity_override": severity,
            "severity": severity,
            "category": category,
            "rule_id": matched_rule.get("id") if matched_rule else None,
            "rule_reason": matched_rule.get("reason") if matched_rule else None,
            "department_name": department_name,
        },
    )
    db.add(anomaly)
    await db.commit()
    await db.refresh(anomaly)

    # Broadcast alert
    from app.services.ws_broadcaster import broadcast_anomaly
    await broadcast_anomaly({
        "employee_id": str(device.employee_id),
        "employee_name": employee.full_name if employee else None,
        "type": "blocked_site_accessed",
        "description": description,
        "severity": severity,
    })

    log.warning("blocked_site_accessed",
                employee_id=str(device.employee_id),
                employee_name=employee.full_name if employee else None,
                domain=reported_domain)

    # Instruct agent to immediately capture a violation screenshot
    return {
        "status": "logged",
        "screenshot_requested": True,
        "trigger": "violation",
        "anomaly_id": str(anomaly.id),
        "employee_id": str(device.employee_id),
        "employee_name": employee.full_name if employee else None,
        "domain": reported_domain,
    }


@router.get("/violations/summary")
async def get_violation_summary(
    days: int = Query(default=1, ge=1, le=90),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """DB-backed summary of blocked-site violations grouped by domain."""
    rows = await _blocked_violation_rows(db, days=days, limit=2000)
    summary: dict[str, dict[str, Any]] = {}

    for anomaly, employee_name, employee_email, _department_name, _hostname in rows:
        metadata = anomaly.event_metadata or {}
        domains = _metadata_domains(metadata)
        if not domains:
            continue

        for domain in domains:
            detail = _domain_detail(metadata, domain)
            rule = _find_block_rule(domain) or {}
            entry = summary.setdefault(
                domain,
                {
                    "domain": domain,
                    "count": 0,
                    "category": detail.get("category") or metadata.get("category") or rule.get("category", "general"),
                    "severity": metadata.get("severity_override") or metadata.get("severity") or detail.get("severity") or rule.get("severity", "medium"),
                    "last_seen": anomaly.detected_at.isoformat(),
                    "employees": {},
                },
            )
            entry["count"] += 1
            if anomaly.detected_at.isoformat() > entry["last_seen"]:
                entry["last_seen"] = anomaly.detected_at.isoformat()

            employee_key = str(anomaly.employee_id)
            employees = entry["employees"]
            if employee_key not in employees:
                employees[employee_key] = {
                    "employee_id": employee_key,
                    "employee_name": employee_name,
                    "employee_email": employee_email,
                    "count": 0,
                }
            employees[employee_key]["count"] += 1

    violations = []
    for entry in summary.values():
        employees = sorted(
            entry["employees"].values(),
            key=lambda item: (-item["count"], item.get("employee_name") or ""),
        )
        violations.append({
            **{key: value for key, value in entry.items() if key != "employees"},
            "employee_count": len(employees),
            "employees": employees[:5],
        })

    violations.sort(key=lambda x: (-x["count"], x["domain"]))
    return violations


@router.get("/violations", response_model=List[dict])
async def list_blocked_site_violations(
    days: int = Query(default=7, ge=1, le=90),
    employee_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Detailed blocked-site violation feed for managers/admins."""
    rows = await _blocked_violation_rows(db, days=days, employee_id=employee_id, limit=limit)
    return [
        _serialize_violation(anomaly, employee_name, employee_email, department_name, hostname)
        for anomaly, employee_name, employee_email, department_name, hostname in rows
    ]
