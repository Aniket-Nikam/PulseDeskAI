import uuid
import secrets
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models import Device, Employee, DeviceStatus
from app.schemas import DeviceEnrollRequest, DeviceEnrollResponse, DeviceApproval, DeviceOut
from app.api.v1.routes.auth import get_current_admin
from app.core.security import generate_device_token
from app.services.online_tracker import is_device_online
from app.core.logging import get_logger

router = APIRouter(prefix="/devices", tags=["devices"])
log = get_logger("devices")


@router.post("/enroll", response_model=DeviceEnrollResponse, status_code=201)
async def enroll_device(
    payload: DeviceEnrollRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the agent on first run. No admin auth required —
    device enters 'pending' state until admin approves.
    """
    result = await db.execute(
        select(Employee).where(Employee.email == payload.employee_email, Employee.is_active == True)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found or not active")

    # Check for existing pending/approved device with same hostname
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
            return DeviceEnrollResponse(
                device_id=existing_device.id,
                device_token=existing_device.device_token,
                status="approved",
                message="Device already enrolled and approved",
            )
        else:
            return DeviceEnrollResponse(
                device_id=existing_device.id,
                device_token=existing_device.device_token,
                status="pending",
                message="Enrollment pending admin approval. Show code to your admin: "
                        + (existing_device.enrollment_code or ""),
            )

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

    log.info("device_enrolled", device_id=str(device.id), employee=payload.employee_email)
    return DeviceEnrollResponse(
        device_id=device.id,
        device_token=token,
        status="pending",
        message=f"Enrollment pending. Show this code to your admin: {enrollment_code}",
    )


@router.get("", response_model=List[DeviceOut])
async def list_devices(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device, Employee.full_name.label("employee_name"))
        .join(Employee, Device.employee_id == Employee.id)
        .order_by(Device.created_at.desc())
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
    return out


@router.get("/pending", response_model=List[DeviceOut])
async def list_pending_devices(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device, Employee.full_name.label("employee_name"))
        .join(Employee, Device.employee_id == Employee.id)
        .where(Device.status == DeviceStatus.pending)
        .order_by(Device.created_at.desc())
    )
    rows = result.all()
    return [
        DeviceOut(
            id=d.id, employee_id=d.employee_id, employee_name=emp,
            hostname=d.hostname, platform=d.platform, os_version=d.os_version,
            agent_version=d.agent_version, status=d.status,
            last_heartbeat=d.last_heartbeat, enrolled_at=d.enrolled_at,
            created_at=d.created_at, is_online=False,
        )
        for d, emp in rows
    ]


@router.patch("/{device_id}/status", response_model=DeviceOut)
async def update_device_status(
    device_id: uuid.UUID,
    payload: DeviceApproval,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if payload.status not in ("approved", "revoked", "suspended"):
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
    device.status = payload.status
    if payload.status == "approved" and not device.enrolled_at:
        device.enrolled_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(device)
    log.info("device_status_updated", device_id=str(device_id), status=payload.status, by=str(admin.id))

    return DeviceOut(
        id=device.id, employee_id=device.employee_id, employee_name=emp_name,
        hostname=device.hostname, platform=device.platform, os_version=device.os_version,
        agent_version=device.agent_version, status=device.status,
        last_heartbeat=device.last_heartbeat, enrolled_at=device.enrolled_at,
        created_at=device.created_at, is_online=is_device_online(device),
    )


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: uuid.UUID,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = DeviceStatus.revoked
    await db.commit()
