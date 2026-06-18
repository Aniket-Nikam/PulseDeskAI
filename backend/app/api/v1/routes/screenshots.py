"""
Screenshot upload, policy management, and auto-capture.
Agent uploads screenshots. Admin views them with auth.
"""

import uuid
import os
import io
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Device, DeviceStatus, Screenshot, ScreenshotPolicy, SnapshotPolicy
from app.schemas import PolicyCreate
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decode_token, device_token_lookup_values, check_admin_can_view_employee
from app.core.files import safe_path_join, sanitize_filename_component
from app.core.rate_limit import enforce_rate_limit
from app.core.agent_auth import verify_agent_request_signature
from app.core.audit import log_admin_action
from app.models import Admin as AdminModel
from jose import JWTError

router = APIRouter(tags=["screenshots"])
log = get_logger("screenshots")

os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)


def _safe_file_exists(file_path: str) -> bool:
    try:
        return safe_path_join(settings.SCREENSHOT_DIR, file_path).exists()
    except HTTPException:
        return False


def _save_file(file_path, data) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(data)


def _extract_device_token_from_request(request: Request, provided_token: str | None = None) -> str:
    token = (provided_token or "").strip()
    if token:
        return token

    header_token = (request.headers.get("x-device-token") or "").strip()
    if header_token:
        return header_token

    auth_header = (request.headers.get("authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return ""


@router.post("/agent/screenshot", status_code=201)
async def upload_screenshot(
    request: Request,
    device_token: str = Form(...),
    captured_at: str = Form(...),
    trigger: str = Form(default="interval"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="agent_screenshot_upload",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        include_auth_fingerprint=False,
        custom_identifier=device_token,
    )
    await verify_agent_request_signature(request, device_token)

    result = await db.execute(select(Device).where(Device.device_token.in_(device_token_lookup_values(device_token))))
    device = result.scalar_one_or_none()
    if not device or device.status != DeviceStatus.approved:
        raise HTTPException(status_code=401, detail="Device not authorized")
    if not device.monitoring_consent_given:
        raise HTTPException(status_code=403, detail="Monitoring consent required")

    if file.content_type not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(status_code=400, detail="Unsupported image content type")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Screenshot upload exceeds max size")
    file_ext = "png" if file.content_type == "image/png" else "jpg"

    # TODO: Background Task
    # Moving the `_compress_image` call and the file I/O `f.write()` to a background 
    # worker (like Celery/Arq) will significantly improve the endpoint's response time 
    # and reduce blocking of the FastAPI worker threads.
    # Try to compress with Pillow if available
    import asyncio
    try:
        if len(contents) > settings.SCREENSHOT_MAX_SIZE_KB * 1024:
            contents = await asyncio.to_thread(_compress_image, contents, settings.SCREENSHOT_MAX_SIZE_KB)
            file_ext = "jpg"
    except Exception as e:
        log.warning("screenshot_compression_failed", error=str(e))

    shot_id = uuid.uuid4()
    filename = sanitize_filename_component(f"{device.employee_id}_{shot_id}.{file_ext}")
    filepath = safe_path_join(settings.SCREENSHOT_DIR, filename)

    # ✅ TRANSACTION: Save file first, then DB record with proper rollback on failure
    try:
        # Step 1: Write file to disk
        await asyncio.to_thread(_save_file, filepath, contents)
        
        # Step 2: Parse timestamp
        try:
            ts = datetime.fromisoformat(captured_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        # Step 3: Create and save DB record
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
        
    except Exception as e:
        # ✅ ROLLBACK: Clean up on failure to prevent orphaned files
        await db.rollback()
        if filepath.exists():
            try:
                os.remove(filepath)
                log.info("orphaned_screenshot_cleaned", file=filename)
            except OSError as cleanup_err:
                log.error("failed_to_cleanup_orphaned_file", file=filename, error=str(cleanup_err))
        log.error("screenshot_save_failed", error=str(e), file=filename)
        raise HTTPException(status_code=500, detail="Failed to save screenshot. Please retry.")
    
    # TRIGGER ASYNC AI ANALYSIS
    try:
        from app.services.screenshot_ai import process_screenshot_with_ai_task
        import asyncio
        asyncio.create_task(process_screenshot_with_ai_task(shot_id))
    except Exception as e:
        log.error(f"failed to start async screenshot AI task: {e}")

    return {"id": str(shot_id), "status": "saved"}


@router.get("/screenshots/{employee_id}", response_model=dict)
async def list_screenshots(
    employee_id: uuid.UUID,
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=21, ge=1, le=200),
    sort: str = Query(default="desc"),
    date: str = Query(default=None, description="Filter by date YYYY-MM-DD"),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """
    List screenshots for an employee with privacy controls.
    Admins can only view screenshots for employees they have access to.
    """
    from sqlalchemy import func
    from datetime import datetime, timedelta

    enforce_rate_limit(
        request,
        key_prefix="admin_screenshot_list",
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        include_auth_fingerprint=True,
    )

    # ✅ PRIVACY CHECK: Verify admin has access to this employee's data
    can_access = await check_admin_can_view_employee(
        admin_id=admin.id,
        admin_role=admin.role.value,
        employee_id=employee_id,
        db=db,
    )
    
    if not can_access:
        log.warning(
            "unauthorized_screenshot_access",
            admin_id=str(admin.id),
            admin_role=admin.role.value,
            employee_id=str(employee_id),
            action="list_screenshots",
        )
        raise HTTPException(status_code=403, detail="You do not have access to view screenshots for this employee")

    base_filter = Screenshot.employee_id == employee_id
    filters = [base_filter]

    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d")
            next_day = day + timedelta(days=1)
            filters.append(Screenshot.captured_at >= day)
            filters.append(Screenshot.captured_at < next_day)
        except ValueError:
            pass

    count_result = await db.execute(
        select(func.count(Screenshot.id)).where(*filters)
    )
    total = count_result.scalar() or 0

    query = select(Screenshot).where(*filters)
    if sort == "asc":
        query = query.order_by(Screenshot.captured_at.asc())
    else:
        query = query.order_by(Screenshot.captured_at.desc())

    result = await db.execute(query.offset(skip).limit(limit))
    shots = result.scalars().all()

    items = [
        {
            "id": str(s.id),
            "captured_at": s.captured_at.isoformat(),
            "trigger": s.trigger,
            "file_size_bytes": s.file_size_bytes,
            "url": f"/api/v1/screenshots/view/{s.id}",
            "file_exists": _safe_file_exists(s.file_path),
        }
        for s in shots
    ]
    payload = {
        "items": items,
        "total": total,
        "page": (skip // limit) + 1,
        "page_size": limit,
        "pages": max((total + limit - 1) // limit, 1),
    }
    log_admin_action(
        "screenshot_list_viewed",
        admin_id=str(admin.id),
        employee_id=str(employee_id),
        count=len(items),
    )
    return payload


@router.get("/screenshots/view/{screenshot_id}")
async def view_screenshot(
    screenshot_id: uuid.UUID,
    request: Request,
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve a screenshot image with privacy controls.
    
    Admin can only view if they have access to that employee's data.
    
    Accepts auth via:
      - Authorization: Bearer <token>  header  (API calls)
      - ?token=<jwt>  query parameter          (<img src> tags)
    """
    # Accept Bearer token header for API clients; query token for <img src> tags.
    if token and not settings.SCREENSHOT_QUERY_TOKEN_ENABLED:
        token = None

    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get(settings.ACCESS_COOKIE_NAME)

    enforce_rate_limit(
        request,
        key_prefix="admin_screenshot_view",
        limit=settings.RATE_LIMIT_PER_MINUTE * 3,
        window_seconds=60,
        include_auth_fingerprint=True,
        custom_identifier=token or None,
    )

    # Validate token
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
            select(AdminModel).where(AdminModel.id == admin_id, AdminModel.is_active)
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

    # ✅ PRIVACY CHECK: Verify admin has access to this employee's screenshot
    can_access = await check_admin_can_view_employee(
        admin_id=admin.id,
        admin_role=admin.role.value,
        employee_id=shot.employee_id,
        db=db,
    )
    
    if not can_access:
        log.warning(
            "unauthorized_screenshot_access",
            admin_id=str(admin.id),
            admin_role=admin.role.value,
            employee_id=str(shot.employee_id),
            screenshot_id=str(screenshot_id),
            action="view_screenshot",
        )
        raise HTTPException(status_code=403, detail="You do not have access to view this screenshot")

    filepath = safe_path_join(settings.SCREENSHOT_DIR, shot.file_path)
    # ✅ VALIDATION: Verify file still exists and is readable
    if not filepath.exists():
        log.warning("screenshot_file_missing_on_disk", screenshot_id=str(shot.id), file_path=shot.file_path)
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    if not filepath.is_file():
        log.warning("screenshot_path_not_file", screenshot_id=str(shot.id), file_path=shot.file_path)
        raise HTTPException(status_code=404, detail="Invalid file path")
    
    # Verify file is readable
    if not os.access(filepath, os.R_OK):
        log.warning("screenshot_file_not_readable", screenshot_id=str(shot.id), file_path=shot.file_path)
        raise HTTPException(status_code=403, detail="Cannot read screenshot file")

    log_admin_action(
        "screenshot_viewed",
        admin_id=str(admin.id),
        screenshot_id=str(shot.id),
        employee_id=str(shot.employee_id),
    )

    media_type = "image/png" if filepath.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(str(filepath), media_type=media_type)


@router.delete("/screenshots/cleanup-missing", status_code=200)
async def cleanup_missing_screenshots(
    request: Request,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Remove all DB records whose files no longer exist on disk."""
    enforce_rate_limit(
        request,
        key_prefix="admin_screenshot_cleanup",
        limit=max(5, settings.RATE_LIMIT_PER_MINUTE // 4),
        window_seconds=60,
        include_auth_fingerprint=True,
    )

    result = await db.execute(select(Screenshot))
    all_shots = result.scalars().all()

    removed = 0
    for shot in all_shots:
        filepath = safe_path_join(settings.SCREENSHOT_DIR, shot.file_path)
        if not filepath.exists():
            await db.delete(shot)
            removed += 1

    await db.commit()
    log.info("cleanup_missing_screenshots", removed=removed, admin=str(admin.id))
    log_admin_action("cleanup_missing_screenshots", admin_id=str(admin.id), removed=removed)
    return {"status": "cleaned", "removed": removed}


@router.delete("/screenshots/{screenshot_id}", status_code=200)
async def delete_screenshot(
    screenshot_id: uuid.UUID,
    request: Request,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a single screenshot (DB record + file on disk) with privacy controls.
    Only admins with access to the employee can delete their screenshots.
    """
    enforce_rate_limit(
        request,
        key_prefix="admin_screenshot_delete",
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        include_auth_fingerprint=True,
    )

    result = await db.execute(select(Screenshot).where(Screenshot.id == screenshot_id))
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    # ✅ PRIVACY CHECK: Verify admin has access to this employee's screenshot
    can_access = await check_admin_can_view_employee(
        admin_id=admin.id,
        admin_role=admin.role.value,
        employee_id=shot.employee_id,
        db=db,
    )
    
    if not can_access:
        log.warning(
            "unauthorized_screenshot_access",
            admin_id=str(admin.id),
            admin_role=admin.role.value,
            employee_id=str(shot.employee_id),
            screenshot_id=str(screenshot_id),
            action="delete_screenshot",
        )
        raise HTTPException(status_code=403, detail="You do not have access to delete this screenshot")

    # Remove file from disk if it exists
    filepath = safe_path_join(settings.SCREENSHOT_DIR, shot.file_path)
    if filepath.exists():
        try:
            os.remove(filepath)
            log.info("screenshot_file_deleted", file=shot.file_path)
        except OSError as e:
            log.error("screenshot_file_delete_failed", file=shot.file_path, error=str(e))

    # Remove DB record
    await db.delete(shot)
    await db.commit()
    log.info("screenshot_deleted", id=str(screenshot_id), admin=str(admin.id))
    log_admin_action("screenshot_deleted", admin_id=str(admin.id), screenshot_id=str(screenshot_id), employee_id=str(shot.employee_id))
    return {"status": "deleted", "id": str(screenshot_id)}



@router.post("/screenshot-policies", status_code=201)
async def create_policy(
    payload: PolicyCreate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    policy_kind = SnapshotPolicy(payload.policy_type)
    is_enabled = policy_kind != SnapshotPolicy.disabled

    # Keep at most one enabled policy at a time for predictable agent behavior.
    if is_enabled:
        active_result = await db.execute(
            select(ScreenshotPolicy).where(ScreenshotPolicy.is_active)
        )
        for existing_policy in active_result.scalars().all():
            existing_policy.is_active = False

    policy = ScreenshotPolicy(
        name=payload.name,
        policy_type=policy_kind,
        interval_minutes=payload.interval_minutes,
        applies_to_all=payload.applies_to_all,
        department_id=payload.department_id,
        employee_id=payload.employee_id,
        is_active=is_enabled,
        created_by=admin.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    log_admin_action("screenshot_policy_created", admin_id=str(admin.id), policy_id=str(policy.id))
    return {
        "id": str(policy.id),
        "name": policy.name,
        "policy_type": policy.policy_type,
        "is_active": policy.is_active,
    }


@router.get("/screenshot-policies", response_model=List[dict])
async def list_policies(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScreenshotPolicy)
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


@router.patch("/screenshot-policies/{policy_id}/toggle", response_model=dict)
async def toggle_policy(
    policy_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ScreenshotPolicy).where(ScreenshotPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
        
    if policy.is_active:
        # "Disable" should stop screenshot capture fully.
        active_result = await db.execute(
            select(ScreenshotPolicy).where(ScreenshotPolicy.is_active)
        )
        for existing_policy in active_result.scalars().all():
            existing_policy.is_active = False
    else:
        # Re-enable selected policy and disable all others.
        active_result = await db.execute(
            select(ScreenshotPolicy).where(
                ScreenshotPolicy.is_active,
                ScreenshotPolicy.id != policy.id,
            )
        )
        for existing_policy in active_result.scalars().all():
            existing_policy.is_active = False
        policy.is_active = True

    await db.commit()
    log_admin_action("screenshot_policy_toggled", admin_id=str(admin.id), policy_id=str(policy.id), new_status=policy.is_active)
    return {"id": str(policy.id), "is_active": policy.is_active}


@router.delete("/screenshot-policies/{policy_id}", status_code=200)
async def delete_policy(
    policy_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ScreenshotPolicy).where(ScreenshotPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
        
    await db.delete(policy)
    await db.commit()
    log_admin_action("screenshot_policy_deleted", admin_id=str(admin.id), policy_id=str(policy_id))
    return {"status": "deleted", "id": str(policy_id)}


@router.get("/agent/screenshot-required")
async def check_screenshot_required(
    request: Request,
    device_token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Agent polls this to know if it should take a screenshot now."""
    resolved_token = _extract_device_token_from_request(request, device_token)
    if not resolved_token:
        return {"required": False}

    enforce_rate_limit(
        request,
        key_prefix="agent_screenshot_required",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=resolved_token,
    )
    await verify_agent_request_signature(request, resolved_token)

    result = await db.execute(
        select(Device).where(
            Device.device_token.in_(device_token_lookup_values(resolved_token)),
            Device.status == DeviceStatus.approved,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        return {"required": False}
    if not device.monitoring_consent_given:
        return {"required": False}

    # Effective policy is the latest enabled policy.
    policy_result = await db.execute(
        select(ScreenshotPolicy).where(
            ScreenshotPolicy.is_active
        ).order_by(ScreenshotPolicy.created_at.desc()).limit(1)
    )
    policy = policy_result.scalar_one_or_none()
    if not policy or policy.policy_type != SnapshotPolicy.interval:
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
        resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', 1)
        img.thumbnail((max_dim, max_dim), resample)
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
