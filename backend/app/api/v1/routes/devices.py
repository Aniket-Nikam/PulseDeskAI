import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import DeviceEnrollRequest, DeviceEnrollResponse, DeviceApproval, DeviceOut, PaginatedResponse
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.logging import get_logger
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.audit import log_admin_action
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["devices"])
log = get_logger("devices")


@router.post("/enroll", response_model=DeviceEnrollResponse, status_code=201)
async def enroll_device(
    payload: DeviceEnrollRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the agent on first run. No admin auth required —
    device enters 'pending' state until admin approves.
    """
    enforce_rate_limit(
        request,
        key_prefix="device_enroll",
        limit=settings.ENROLLMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )

    if len(payload.hostname.strip()) > 255:
        raise HTTPException(status_code=400, detail="hostname is too long")

    result = await device_service.enroll_device(payload, db)

    log.info("device_enrollment_attempt", device_id=result["device_id"], status=result["status"])
    return DeviceEnrollResponse(
        device_id=uuid.UUID(result["device_id"]),
        device_token=result["device_token"],
        status=result["status"],
        message=result["message"],
    )


@router.get("", response_model=PaginatedResponse[DeviceOut])
async def list_devices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    items, total = await device_service.list_devices(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=items,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.get("/pending", response_model=PaginatedResponse[DeviceOut])
async def list_pending_devices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    items, total = await device_service.list_pending_devices(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=items,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        pages=(total + limit - 1) // limit,
    )


@router.patch("/{device_id}/status", response_model=DeviceOut)
async def update_device_status(
    device_id: uuid.UUID,
    payload: DeviceApproval,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    device_out = await device_service.update_device_status(device_id, payload.status, db)
    log.info("device_status_updated", device_id=str(device_id), status=payload.status, by=str(admin.id))
    log_admin_action(
        "device_status_updated",
        admin_id=str(admin.id),
        device_id=str(device_id),
        status=payload.status,
    )
    return device_out


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    await device_service.delete_device(device_id, db)
    log_admin_action("device_deleted", admin_id=str(admin.id), device_id=str(device_id))
