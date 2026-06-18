"""
Zero-config enrollment flow.
Admin generates a join token → employee runs:
    python agent.py --join http://server/api/v1/enroll/join/TOKEN

The token embeds server URL + pre-approves the device on first connect.
"""

import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Employee, Device, DeviceStatus
from app.core.security import generate_device_token, generate_one_time_token, hash_device_token
from app.api.v1.routes.auth import require_admin_write, require_admin_read
from app.core.logging import get_logger
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.audit import log_admin_action
from app.services.token_store import token_store

router = APIRouter(prefix="/enroll", tags=["enrollment"])
log = get_logger("enrollment")

JOIN_TOKEN_KIND = "agent_join_url_token"


def _normalize_server_url(server_url: str) -> str:
    candidate = (server_url or "").strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="server_url must be a valid absolute http(s) URL")
    return candidate


@router.post("/generate-link")
async def generate_join_link(
    request: Request,
    employee_id: uuid.UUID,
    server_url: str | None = None,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin generates a one-time join link for an employee.
    Link expires based on ENROLLMENT_LINK_TTL_HOURS.
    """
    enforce_rate_limit(
        request,
        key_prefix="enrollment_generate",
        limit=settings.ENROLLMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        include_auth_fingerprint=True,
    )

    result = await db.execute(select(Employee).where(Employee.id == employee_id, Employee.is_active))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    resolved_server_url = _normalize_server_url(server_url or str(request.base_url))
    token = generate_one_time_token(24)
    token_store.issue(
        kind=JOIN_TOKEN_KIND,
        token=token,
        payload={
            "employee_id": str(employee_id),
            "employee_email": employee.email,
            "employee_name": employee.full_name,
            "server_url": resolved_server_url,
        },
        ttl_seconds=settings.ENROLLMENT_LINK_TTL_HOURS * 3600,
    )

    join_url = f"{resolved_server_url}/api/v1/enroll/join/{token}"
    install_cmd = f'python agent.py --join "{join_url}"'

    log.info("join_link_generated", employee_id=str(employee_id), token_hint=token[:6])
    log_admin_action(
        "enrollment_link_generated",
        admin_id=str(admin.id),
        employee_id=str(employee_id),
    )
    return {
        "token": token,
        "join_url": join_url,
        "install_command": install_cmd,
        "employee_name": employee.full_name,
        "employee_email": employee.email,
        "expires_in_hours": settings.ENROLLMENT_LINK_TTL_HOURS,
        "instructions": [
            "1. Copy the install_command below",
            "2. Run it on the employee's machine (Python must be installed)",
            "3. The device will auto-enroll and be pre-approved",
            "4. No configuration files needed",
        ],
    }


@router.get("/join/{token}")
async def get_join_config(token: str, db: AsyncSession = Depends(get_db)):
    """
    Agent calls this URL to get its configuration.
    Returns server URL + employee email + pre-approved device token.
    """
    active = token_store.get(kind=JOIN_TOKEN_KIND, token=token)
    if not active:
        consumed = token_store.get(kind=JOIN_TOKEN_KIND, token=token, allow_consumed=True)
        if consumed and consumed.is_consumed:
            raise HTTPException(status_code=410, detail="Join token already used")
        raise HTTPException(status_code=404, detail="Invalid or expired join token")

    if not token_store.consume(kind=JOIN_TOKEN_KIND, token=token):
        raise HTTPException(status_code=410, detail="Join token already used")

    # Auto-create and approve the device
    employee_id = uuid.UUID(active.payload["employee_id"])
    device_id = uuid.uuid4()
    device_token = generate_device_token(str(device_id), str(employee_id))

    device = Device(
        id=device_id,
        employee_id=employee_id,
        hostname="pending",  # agent will update on first heartbeat
        platform="unknown",
        device_token=hash_device_token(device_token),
        status=DeviceStatus.approved,  # pre-approved!
        enrolled_at=datetime.now(timezone.utc),
    )
    db.add(device)
    await db.commit()

    log.info("device_auto_enrolled", employee_id=str(employee_id), device_id=str(device_id))

    return {
        "server_url": active.payload["server_url"],
        "employee_email": active.payload["employee_email"],
        "device_token": device_token,
        "device_id": str(device_id),
        "status": "approved",
        "message": f"Welcome {active.payload['employee_name']}! Your device is enrolled and approved.",
    }


@router.get("/tokens/active")
async def list_active_tokens(admin=Depends(require_admin_read)):
    """Show all active (unexpired) join tokens."""
    active_records = token_store.active_records(kind=JOIN_TOKEN_KIND)
    return [
        {
            "employee_name": rec.payload.get("employee_name"),
            "employee_email": rec.payload.get("employee_email"),
            "expires_at": rec.expires_at.isoformat(),
            "created_at": rec.created_at.isoformat(),
        }
        for rec in active_records
    ]
