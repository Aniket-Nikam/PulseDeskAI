"""
Screenshot upload, policy management, and auto-capture.
Agent uploads screenshots. Admin views them with auth.
"""

import uuid
import os
import io
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete

from app.db.session import get_db
from app.models import Device, DeviceStatus, Screenshot, ScreenshotPolicy, SnapshotPolicy
from app.schemas import PolicyCreate
from app.api.v1.routes.auth import get_current_admin
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decode_token
from app.models import Admin as AdminModel
from jose import JWTError

router = APIRouter(tags=["screenshots"])
log = get_logger("screenshots")

os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)


@router.post("/agent/screenshot", status_code=201)
async def upload_screenshot(
    device_token: str = Form(...),
    captured_at: str = Form(...),
    trigger: str = Form(default="interval"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Device).where(Device.device_token == device_token))
    device = result.scalar_one_or_none()
    if not device or device.status != DeviceStatus.approved:
        raise HTTPException(status_code=401, detail="Device not authorized")

    contents = await file.read()

    # Try to compress with Pillow if available
    try:
        from PIL import Image
        if len(contents) > settings.SCREENSHOT_MAX_SIZE_KB * 1024:
            contents = _compress_image(contents, settings.SCREENSHOT_MAX_SIZE_KB)
    except ImportError:
        pass  # Pillow not installed, save as-is

    shot_id = uuid.uuid4()
    filename = f"{device.employee_id}_{shot_id}.jpg"
    filepath = os.path.join(settings.SCREENSHOT_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    try:
        ts = datetime.fromisoformat(captured_at)
    except ValueError:
        ts = datetime.now(timezone.utc)

    screenshot = Screenshot(
        id=shot_id,
        employee_id=device.employee_id,
        device_id=device.id,
        captured_at=ts,
        file_path=filename,
        file_size_bytes=len(contents),
        trigger=trigger,
    )
    db.add(screenshot)
    await db.commit()
    log.info("screenshot_saved", employee_id=str(device.employee_id), size_bytes=len(contents))
    return {"id": str(shot_id), "status": "saved"}


@router.get("/screenshots/{employee_id}", response_model=List[dict])
async def list_screenshots(
    employee_id: uuid.UUID,
    limit: int = 50,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Screenshot)
        .where(Screenshot.employee_id == employee_id)
        .order_by(Screenshot.captured_at.desc())
        .limit(limit)
    )
    shots = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "captured_at": s.captured_at.isoformat(),
            "trigger": s.trigger,
            "file_size_bytes": s.file_size_bytes,
            "url": f"/api/v1/screenshots/view/{s.id}",
            "file_exists": os.path.exists(
                os.path.join(settings.SCREENSHOT_DIR, s.file_path)
            ),
        }
        for s in shots
    ]


@router.get("/screenshots/view/{screenshot_id}")
async def view_screenshot(
    screenshot_id: uuid.UUID,
    token: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve a screenshot image. Accepts auth via:
      - Authorization: Bearer <token>  header  (API calls)
      - ?token=<jwt>  query parameter          (<img src> tags)
    """
    # Validate the token from query parameter
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        result_admin = await db.execute(
            select(AdminModel).where(AdminModel.id == admin_id, AdminModel.is_active == True)
        )
        admin = result_admin.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")

    result = await db.execute(select(Screenshot).where(Screenshot.id == screenshot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    filepath = os.path.join(settings.SCREENSHOT_DIR, shot.file_path)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(filepath, media_type="image/jpeg")


@router.delete("/screenshots/cleanup-missing", status_code=200)
async def cleanup_missing_screenshots(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove all DB records whose files no longer exist on disk."""
    result = await db.execute(select(Screenshot))
    all_shots = result.scalars().all()

    removed = 0
    for shot in all_shots:
        filepath = os.path.join(settings.SCREENSHOT_DIR, shot.file_path)
        if not os.path.exists(filepath):
            await db.delete(shot)
            removed += 1

    await db.commit()
    log.info("cleanup_missing_screenshots", removed=removed, admin=str(admin.id))
    return {"status": "cleaned", "removed": removed}


@router.delete("/screenshots/{screenshot_id}", status_code=200)
async def delete_screenshot(
    screenshot_id: uuid.UUID,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single screenshot (DB record + file on disk)."""
    result = await db.execute(select(Screenshot).where(Screenshot.id == screenshot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    # Remove file from disk if it exists
    filepath = os.path.join(settings.SCREENSHOT_DIR, shot.file_path)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            log.info("screenshot_file_deleted", file=shot.file_path)
        except OSError as e:
            log.error("screenshot_file_delete_failed", file=shot.file_path, error=str(e))

    # Remove DB record
    await db.delete(shot)
    await db.commit()
    log.info("screenshot_deleted", id=str(screenshot_id), admin=str(admin.id))
    return {"status": "deleted", "id": str(screenshot_id)}



@router.post("/screenshot-policies", status_code=201)
async def create_policy(
    payload: PolicyCreate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    policy = ScreenshotPolicy(
        name=payload.name,
        policy_type=payload.policy_type,
        interval_minutes=payload.interval_minutes,
        applies_to_all=payload.applies_to_all,
        department_id=payload.department_id,
        employee_id=payload.employee_id,
        created_by=admin.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return {"id": str(policy.id), "name": policy.name, "policy_type": policy.policy_type}


@router.get("/screenshot-policies", response_model=List[dict])
async def list_policies(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScreenshotPolicy)
        .where(ScreenshotPolicy.is_active == True)
        .order_by(ScreenshotPolicy.created_at.desc())
    )
    policies = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "policy_type": p.policy_type,
            "interval_minutes": p.interval_minutes,
            "applies_to_all": p.applies_to_all,
            "department_id": str(p.department_id) if p.department_id else None,
            "employee_id": str(p.employee_id) if p.employee_id else None,
            "is_active": p.is_active,
        }
        for p in policies
    ]


@router.get("/agent/screenshot-required")
async def check_screenshot_required(device_token: str, db: AsyncSession = Depends(get_db)):
    """Agent polls this to know if it should take a screenshot now."""
    result = await db.execute(
        select(Device).where(Device.device_token == device_token, Device.status == DeviceStatus.approved)
    )
    device = result.scalar_one_or_none()
    if not device:
        return {"required": False}

    # Check for active interval policy
    policy_result = await db.execute(
        select(ScreenshotPolicy).where(
            ScreenshotPolicy.is_active == True,
            ScreenshotPolicy.policy_type == SnapshotPolicy.interval,
        ).limit(1)
    )
    policy = policy_result.scalar_one_or_none()
    if not policy:
        return {"required": False}

    # Check if enough time has passed since last screenshot
    last_result = await db.execute(
        select(Screenshot)
        .where(Screenshot.employee_id == device.employee_id)
        .order_by(Screenshot.captured_at.desc())
        .limit(1)
    )
    last = last_result.scalar_one_or_none()

    if not last:
        return {"required": True, "interval_minutes": policy.interval_minutes}

    elapsed = (datetime.now(timezone.utc) - last.captured_at).total_seconds() / 60
    return {
        "required": elapsed >= (policy.interval_minutes or 10),
        "interval_minutes": policy.interval_minutes,
        "last_taken_minutes_ago": round(elapsed, 1),
    }


def _compress_image(data: bytes, max_kb: int) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("RGB")
    max_dim = 1280
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    quality = 75
    while quality > 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        result = buf.getvalue()
        if len(result) <= max_kb * 1024:
            return result
        quality -= 10
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=20)
    return buf.getvalue()
