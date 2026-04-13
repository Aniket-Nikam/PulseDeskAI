"""
Zero-config enrollment flow.
Admin generates a join token → employee runs:
    python agent.py --join http://server/api/v1/enroll/join/TOKEN

The token embeds server URL + pre-approves the device on first connect.
"""

import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Employee, Device, DeviceStatus
from app.core.security import generate_device_token
from app.api.v1.routes.auth import get_current_admin
from app.core.logging import get_logger

router = APIRouter(prefix="/enroll", tags=["enrollment"])
log = get_logger("enrollment")

# In-memory join token store (use Redis in production)
# token -> {employee_id, expires_at, server_url}
_join_tokens: dict = {}


@router.post("/generate-link")
async def generate_join_link(
    employee_id: uuid.UUID,
    server_url: str = "http://localhost:8000",
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin generates a one-time join link for an employee.
    Link expires in 24 hours.
    """
    result = await db.execute(select(Employee).where(Employee.id == employee_id, Employee.is_active == True))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    token = secrets.token_urlsafe(16)
    _join_tokens[token] = {
        "employee_id": str(employee_id),
        "employee_email": employee.email,
        "employee_name": employee.full_name,
        "server_url": server_url.rstrip("/"),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
    }

    join_url = f"{server_url.rstrip('/')}/api/v1/enroll/join/{token}"
    install_cmd = f'python agent.py --join "{join_url}"'

    log.info("join_link_generated", employee_id=str(employee_id), token=token[:8] + "...")
    return {
        "token": token,
        "join_url": join_url,
        "install_command": install_cmd,
        "employee_name": employee.full_name,
        "employee_email": employee.email,
        "expires_in_hours": 24,
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
    if token not in _join_tokens:
        raise HTTPException(status_code=404, detail="Invalid or expired join token")

    info = _join_tokens[token]

    # Check expiry
    expires = datetime.fromisoformat(info["expires_at"])
    if datetime.now(timezone.utc) > expires:
        del _join_tokens[token]
        raise HTTPException(status_code=410, detail="Join token has expired")

    # Auto-create and approve the device
    employee_id = uuid.UUID(info["employee_id"])
    device_id = uuid.uuid4()
    device_token = generate_device_token(str(device_id), str(employee_id))

    device = Device(
        id=device_id,
        employee_id=employee_id,
        hostname="pending",  # agent will update on first heartbeat
        platform="unknown",
        device_token=device_token,
        status=DeviceStatus.approved,  # pre-approved!
        enrolled_at=datetime.now(timezone.utc),
    )
    db.add(device)
    await db.commit()

    # Consume token (one-time use)
    del _join_tokens[token]

    log.info("device_auto_enrolled", employee_id=str(employee_id), device_id=str(device_id))

    return {
        "server_url": info["server_url"],
        "employee_email": info["employee_email"],
        "device_token": device_token,
        "device_id": str(device_id),
        "status": "approved",
        "message": f"Welcome {info['employee_name']}! Your device is enrolled and approved.",
    }


@router.get("/tokens/active")
async def list_active_tokens(admin=Depends(get_current_admin)):
    """Show all active (unexpired) join tokens."""
    now = datetime.now(timezone.utc)
    active = []
    for token, info in list(_join_tokens.items()):
        expires = datetime.fromisoformat(info["expires_at"])
        if expires > now:
            active.append({
                "token": token[:8] + "...",
                "employee_name": info["employee_name"],
                "employee_email": info["employee_email"],
                "expires_at": info["expires_at"],
            })
        else:
            del _join_tokens[token]
    return active
