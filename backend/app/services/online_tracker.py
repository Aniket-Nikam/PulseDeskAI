"""
Online tracker: determines if a device/employee is currently online
based on last heartbeat timestamp.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Device, ActivityEvent, DeviceStatus
from app.core.config import settings


def is_device_online(device: Optional[Device]) -> bool:
    """Device is considered online if heartbeat received within timeout window."""
    if not device or not device.last_heartbeat:
        return False
    if device.status != DeviceStatus.approved:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)
    return device.last_heartbeat > cutoff


async def is_employee_online(employee_id: uuid.UUID, db: AsyncSession) -> bool:
    """Returns True if any approved device for this employee is online."""
    result = await db.execute(
        select(Device).where(
            Device.employee_id == employee_id,
            Device.status == DeviceStatus.approved,
        )
    )
    devices = result.scalars().all()
    return any(is_device_online(d) for d in devices)


async def get_employee_last_event(
    employee_id: uuid.UUID,
    db: AsyncSession,
) -> Optional[ActivityEvent]:
    """Returns the most recent activity event for an employee."""
    result = await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.employee_id == employee_id)
        .order_by(ActivityEvent.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
