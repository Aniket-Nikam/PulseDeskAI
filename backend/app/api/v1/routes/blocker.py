"""
Website Blocker System
Admin defines blocked domains → agent enforces them → violations logged as anomalies.

This is rule-based, no ML. Agent checks active window title + app name against blocklist.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models import Device, DeviceStatus
from app.api.v1.routes.auth import get_current_admin
from app.core.logging import get_logger
from pydantic import BaseModel

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
async def list_blocked_domains(admin=Depends(get_current_admin)):
    """List all blocked domains."""
    return list(_blocked_domains.values())


@router.post("/domains", status_code=201)
async def add_blocked_domain(
    payload: BlockedDomain,
    admin=Depends(get_current_admin),
):
    domain_id = str(uuid.uuid4())
    domain = payload.domain.lower().strip().replace("https://", "").replace("http://", "").replace("www.", "")

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
    return _blocked_domains[domain_id]


@router.delete("/domains/{domain_id}", status_code=204)
async def remove_blocked_domain(domain_id: str, admin=Depends(get_current_admin)):
    if domain_id not in _blocked_domains:
        raise HTTPException(status_code=404, detail="Domain not found")
    del _blocked_domains[domain_id]


@router.patch("/domains/{domain_id}/toggle")
async def toggle_domain(domain_id: str, admin=Depends(get_current_admin)):
    if domain_id not in _blocked_domains:
        raise HTTPException(status_code=404, detail="Domain not found")
    _blocked_domains[domain_id]["is_active"] = not _blocked_domains[domain_id]["is_active"]
    return _blocked_domains[domain_id]


@router.post("/load-defaults", status_code=201)
async def load_default_blocks(admin=Depends(get_current_admin)):
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
async def report_violation(payload: BlockViolation, db: AsyncSession = Depends(get_db)):
    """
    Agent reports when a blocked domain is accessed.
    Creates an anomaly log entry and broadcasts to dashboard.
    """
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

    return {"status": "logged"}


@router.get("/violations/summary")
async def get_violation_summary(admin=Depends(get_current_admin)):
    """Summary of which domains have been accessed most."""
    violations = [
        {"domain": v["domain"], "count": v.get("violation_count", 0), "category": v["category"]}
        for v in _blocked_domains.values()
        if v.get("violation_count", 0) > 0
    ]
    violations.sort(key=lambda x: x["count"], reverse=True)
    return violations
