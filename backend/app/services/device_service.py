import uuid
import secrets
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.models import Device, Employee, DeviceStatus
from app.schemas import DeviceEnrollRequest, DeviceOut
from app.core.security import generate_device_token
from app.services.online_tracker import is_device_online


async def enroll_device(payload: DeviceEnrollRequest, db: AsyncSession) -> dict:
    employee_email = payload.employee_email.strip().lower()
    
    result = await db.execute(
        select(Employee).where(Employee.email == employee_email, Employee.is_active)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found or not active")

    existing = await db.execute(
        select(Device).where(
            Device.employee_id == employee.id,
            Device.hostname == payload.hostname,
            Device.status.in_([DeviceStatus.approved, DeviceStatus.pending]),
        )
    )
    existing_device = existing.scalar_one_or_none()
    if existing_device:
        if existing_device.status == DeviceStatus.approved:
            return {
                "device_id": str(existing_device.id),
                "device_token": existing_device.device_token,
                "status": "approved",
                "message": "Device already enrolled and approved",
            }
        else:
            return {
                "device_id": str(existing_device.id),
                "device_token": existing_device.device_token,
                "status": "pending",
                "message": "Enrollment pending admin approval. Show code to your admin: "
                           + (existing_device.enrollment_code or ""),
            }

    device_id = uuid.uuid4()
    token = generate_device_token(str(device_id), str(employee.id))
    enrollment_code = secrets.token_hex(3).upper()

    device = Device(
        id=device_id,
        employee_id=employee.id,
        hostname=payload.hostname,
        platform=payload.platform,
        os_version=payload.os_version,
        agent_version=payload.agent_version,
        device_token=token,
        enrollment_code=enrollment_code,
        status=DeviceStatus.pending,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)

    return {
        "device_id": str(device.id),
        "device_token": token,
        "status": "pending",
        "message": f"Enrollment pending. Show this code to your admin: {enrollment_code}",
        "employee_email": employee_email
    }


async def list_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> Tuple[List[DeviceOut], int]:
    count_result = await db.execute(select(func.count(Device.id)))
    total = count_result.scalar() or 0
    
    result = await db.execute(
        select(Device, Employee.full_name.label("employee_name"))
        .join(Employee, Device.employee_id == Employee.id)
        .order_by(Device.created_at.desc())
        .offset(skip).limit(limit)
    )
    rows = result.all()
    out = []
    for device, emp_name in rows:
        out.append(DeviceOut(
            id=device.id,
            employee_id=device.employee_id,
            employee_name=emp_name,
            hostname=device.hostname,
            platform=device.platform,
            os_version=device.os_version,
            agent_version=device.agent_version,
            status=device.status,
            last_heartbeat=device.last_heartbeat,
            enrolled_at=device.enrolled_at,
            created_at=device.created_at,
            is_online=is_device_online(device),
        ))
    return out, total


async def list_pending_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> Tuple[List[DeviceOut], int]:
    count_result = await db.execute(select(func.count(Device.id)).where(Device.status == DeviceStatus.pending))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Device, Employee.full_name.label("employee_name"))
        .join(Employee, Device.employee_id == Employee.id)
        .where(Device.status == DeviceStatus.pending)
        .order_by(Device.created_at.desc())
        .offset(skip).limit(limit)
    )
    rows = result.all()
    out = [
        DeviceOut(
            id=d.id, employee_id=d.employee_id, employee_name=emp,
            hostname=d.hostname, platform=d.platform, os_version=d.os_version,
            agent_version=d.agent_version, status=d.status,
            last_heartbeat=d.last_heartbeat, enrolled_at=d.enrolled_at,
            created_at=d.created_at, is_online=False,
        )
        for d, emp in rows
    ]
    return out, total


async def update_device_status(device_id: uuid.UUID, status: str, db: AsyncSession) -> DeviceOut:
    if status not in ("approved", "revoked", "suspended"):
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await db.execute(
        select(Device, Employee.full_name.label("emp_name"))
        .join(Employee, Device.employee_id == Employee.id)
        .where(Device.id == device_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")

    device, emp_name = row
    device.status = status
    if status == "approved" and not device.enrolled_at:
        device.enrolled_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(device)
    
    return DeviceOut(
        id=device.id, employee_id=device.employee_id, employee_name=emp_name,
        hostname=device.hostname, platform=device.platform, os_version=device.os_version,
        agent_version=device.agent_version, status=device.status,
        last_heartbeat=device.last_heartbeat, enrolled_at=device.enrolled_at,
        created_at=device.created_at, is_online=is_device_online(device),
    )


async def delete_device(device_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Nullify device_id on related records to preserve historical data
    # Screenshots, anomalies, etc. belong to the employee — not the device
    from sqlalchemy import update
    from app.models import Screenshot, AnomalyLog, ActivityEvent, WorkSession
    
    await db.execute(update(Screenshot).where(Screenshot.device_id == device_id).values(device_id=None))
    await db.execute(update(AnomalyLog).where(AnomalyLog.device_id == device_id).values(device_id=None))
    await db.execute(update(ActivityEvent).where(ActivityEvent.device_id == device_id).values(device_id=None))
    await db.execute(update(WorkSession).where(WorkSession.device_id == device_id).values(device_id=None))
    
    await db.delete(device)
    await db.commit()
