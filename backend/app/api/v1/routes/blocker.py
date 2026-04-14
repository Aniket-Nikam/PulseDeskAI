"""
Website Blocker System
Admin defines blocked domains → agent enforces them → violations logged as anomalies.

This is rule-based, no ML. Agent checks active window title + app name against blocklist.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Device, DeviceStatus
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.logging import get_logger
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.audit import log_admin_action
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/blocker", tags=["website-blocker"])
log = get_logger("blocker")


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
async def get_active_blocklist():
    """
    Called by agent every 5 minutes to sync its local blocklist.
    No auth required — device token validated separately.
    Returns just the domain strings for efficient matching.
    """
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

    # Increment violation count
    for domain_entry in _blocked_domains.values():
        if domain_entry["domain"] in payload.domain.lower():
            domain_entry["violation_count"] = domain_entry.get("violation_count", 0) + 1

    # Create anomaly via anomaly detector
    from app.models import AnomalyLog, AnomalyType
    anomaly = AnomalyLog(
        employee_id=device.employee_id,
        device_id=device.id,
        anomaly_type=AnomalyType.unusual_app_usage,
        description=f"Blocked site accessed: {payload.domain} via {payload.app_name}. Window: '{payload.window_title}'",
        event_metadata={
            "domain": payload.domain,
            "app_name": payload.app_name,
            "window_title": payload.window_title,
            "violation_type": "blocked_domain",
        },
    )
    db.add(anomaly)
    await db.commit()

    # Broadcast alert
    from app.services.ws_broadcaster import broadcast_anomaly
    await broadcast_anomaly({
        "employee_id": str(device.employee_id),
        "type": "blocked_site_accessed",
        "description": f"Blocked site accessed: {payload.domain}",
        "severity": "high",
    })

    log.warning("blocked_site_accessed",
                employee_id=str(device.employee_id),
                domain=payload.domain)

    # Instruct agent to immediately capture a violation screenshot
    return {"status": "logged", "screenshot_requested": True, "trigger": "violation"}


@router.get("/violations/summary")
async def get_violation_summary(admin=Depends(require_admin_read)):
    """Summary of which domains have been accessed most."""
    violations = [
        {"domain": v["domain"], "count": v.get("violation_count", 0), "category": v["category"]}
        for v in _blocked_domains.values()
        if v.get("violation_count", 0) > 0
    ]
    violations.sort(key=lambda x: x["count"], reverse=True)
    return violations
