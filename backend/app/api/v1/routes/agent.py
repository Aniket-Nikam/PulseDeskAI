"""
PulseDesk Agent Routes v5
Refactored: scoring consolidated, imports cleaned up, background job marked.
"""

import uuid
import socket
import platform as plat
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Device, DeviceStatus, ActivityEvent, WorkSession
from app.schemas import (
    ActivityBatch, BatchResponse,
    SessionStart, SessionEnd,
    HeartbeatIn, HeartbeatOut,
)
from app.services.categorizer import categorize_app
from app.services.anomaly_detector import check_anomalies
from app.services.ws_broadcaster import broadcast_employee_update
from app.services.scoring import compute_session_score
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import device_token_lookup_values
from app.core.rate_limit import enforce_rate_limit
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.services.ws_broadcaster import stream_manager

router = APIRouter(tags=["agent"])
log = get_logger("agent")

class StreamConfigUpdate(BaseModel):
    enabled: bool
    fps: Optional[float] = None
    quality: Optional[int] = None



class DeviceInfoPatchRequest(BaseModel):
    device_token: str = Field(min_length=32, max_length=128)
    hostname: Optional[str] = Field(default=None, max_length=255)
    platform: Optional[str] = Field(default=None, max_length=50)
    os_version: Optional[str] = Field(default=None, max_length=100)
    agent_version: Optional[str] = Field(default=None, max_length=20)


async def _get_approved_device(token: str, db: AsyncSession) -> Device:
    lookup_values = device_token_lookup_values(token)
    if not lookup_values:
        raise HTTPException(status_code=401, detail="Unknown device token")
    result = await db.execute(select(Device).where(Device.device_token.in_(lookup_values)))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device token")
    if device.status != DeviceStatus.approved:
        raise HTTPException(status_code=403, detail=f"Device not approved (status: {device.status})")
    return device


@router.post("/agent/heartbeat", response_model=HeartbeatOut)
async def heartbeat(
    payload: HeartbeatIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="agent_heartbeat",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=payload.device_token,
    )
    device = await _get_approved_device(payload.device_token, db)
    device.last_heartbeat = datetime.now(timezone.utc)

    # Update device info on heartbeat if provided and still unknown
    if hasattr(payload, 'hostname') and payload.hostname:
        if device.hostname in ("pending", "unknown", "", None):
            device.hostname = payload.hostname
    if hasattr(payload, 'platform') and payload.platform:
        if device.platform in ("unknown", "", None):
            device.platform = payload.platform
    if hasattr(payload, 'os_version') and payload.os_version:
        device.os_version = payload.os_version[:100]
    if hasattr(payload, 'agent_version') and payload.agent_version:
        device.agent_version = payload.agent_version

    # Geofence evaluation
    within_geofence = None
    nearest_location_name = None

    if payload.latitude is not None and payload.longitude is not None:
        from app.services.attendance_service import list_locations
        from app.services.geofence import find_nearest_location, haversine_distance

        locations = await list_locations(db)
        active_locs = [
            {
                "id": loc.id,
                "name": loc.name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "radius_meters": loc.radius_meters,
            }
            for loc in locations
            if loc.is_active
        ]

        nearest = find_nearest_location(payload.latitude, payload.longitude, active_locs)
        if nearest:
            within_geofence = True
            nearest_location_name = nearest["name"]
        else:
            within_geofence = False
            if active_locs:
                closest_loc = min(
                    active_locs,
                    key=lambda l: haversine_distance(payload.latitude, payload.longitude, l["latitude"], l["longitude"])
                )
                nearest_location_name = closest_loc["name"]

    # Auto-mark attendance
    from app.services.attendance_service import get_attendance_settings, check_in
    from app.models import AttendanceRecord
    from sqlalchemy import cast, Date

    settings_att = await get_attendance_settings(db)
    if settings_att and settings_att.is_configured:
        now = datetime.now(timezone.utc)
        today_date = now.date()

        # Check if already checked in today (cast to Date for robust comparison)
        res_att = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == device.employee_id,
                cast(AttendanceRecord.date, Date) == today_date,
            )
        )
        existing_record = res_att.scalar_one_or_none()

        if not existing_record or not existing_record.check_in_time:
            # Auto-mark check-in if within geofence OR if remote check-in is allowed
            should_attempt = within_geofence or settings_att.allow_remote_checkin
            if should_attempt:
                try:
                    result = await check_in(
                        db=db,
                        employee_id=device.employee_id,
                        latitude=payload.latitude,
                        longitude=payload.longitude,
                    )
                    if "error" in result:
                        log.info(f"Auto check-in skipped: {result['error']}", employee_id=str(device.employee_id))
                    else:
                        log.info("Auto check-in success", employee_id=str(device.employee_id), status=result.get("status"))
                except Exception as e:
                    log.warning(f"Auto check-in failed: {e}", employee_id=str(device.employee_id))
            else:
                log.debug("Auto check-in skipped: not in geofence and remote check-in disabled", employee_id=str(device.employee_id))

    await db.commit()
    return HeartbeatOut(
        status="ok",
        server_time=datetime.now(timezone.utc),
        screenshot_required=False,
        within_geofence=within_geofence,
        nearest_location_name=nearest_location_name,
    )


@router.patch("/agent/device-info")
async def update_device_info(
    payload: DeviceInfoPatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="agent_device_info",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=payload.device_token,
    )
    token = payload.device_token
    lookup_values = device_token_lookup_values(token)
    if not lookup_values:
        raise HTTPException(status_code=401, detail="Unknown device")
    result = await db.execute(select(Device).where(Device.device_token.in_(lookup_values)))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device")
    if device.status != DeviceStatus.approved:
        raise HTTPException(status_code=403, detail="Device not approved")

    if payload.hostname:
        device.hostname = payload.hostname
    if payload.platform:
        device.platform = payload.platform
    if payload.os_version:
        device.os_version = payload.os_version
    if payload.agent_version:
        device.agent_version = payload.agent_version

    await db.commit()
    log.info("device_info_updated", hostname=device.hostname, platform=device.platform)
    return {"status": "updated", "hostname": device.hostname}


@router.post("/agent/session/start", response_model=dict)
async def start_session(
    payload: SessionStart,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="agent_session_start",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=payload.device_token,
    )
    device = await _get_approved_device(payload.device_token, db)

    # Close any lingering open sessions
    open_result = await db.execute(
        select(WorkSession).where(
            WorkSession.device_id == device.id,
            WorkSession.ended_at.is_(None),
        )
    )
    for s in open_result.scalars().all():
        now = datetime.now(timezone.utc)
        s.ended_at = now
        s.duration_seconds = int((now - s.started_at).total_seconds())

    session = WorkSession(
        employee_id=device.employee_id,
        device_id=device.id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)

    # Increment check-in counter if starting during work hours subsequent times
    try:
        from app.models import Employee, AttendanceRecord
        from sqlalchemy import cast, Date, func
        import zoneinfo

        emp_res = await db.execute(select(Employee).where(Employee.id == device.employee_id))
        emp = emp_res.scalar_one_or_none()
        if emp:
            work_end_hr = getattr(emp, "work_end_hour", 18)
            tz_str = getattr(emp, "timezone", "UTC")
            try:
                tz = zoneinfo.ZoneInfo(tz_str)
            except Exception:
                tz = timezone.utc

            now_utc = datetime.now(timezone.utc)
            local_now = now_utc.astimezone(tz)
            today_date = local_now.date()

            res_att = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id == device.employee_id,
                    cast(AttendanceRecord.date, Date) == today_date,
                )
            )
            record = res_att.scalar_one_or_none()
            if record:
                if local_now.hour < work_end_hr:
                    today_start_utc = datetime(today_date.year, today_date.month, today_date.day, tzinfo=tz).astimezone(timezone.utc)
                    sess_count_res = await db.execute(
                        select(func.count(WorkSession.id)).where(
                            WorkSession.employee_id == device.employee_id,
                            WorkSession.started_at >= today_start_utc,
                        )
                    )
                    session_count = sess_count_res.scalar() or 0
                    if session_count > 0:
                        record.check_in_count = (record.check_in_count or 1) + 1
                        log.info("check_in_count_incremented", employee_id=str(device.employee_id), count=record.check_in_count)
    except Exception as e:
        log.warning(f"failed_to_increment_checkin_count: {e}")

    await db.commit()
    await db.refresh(session)
    log.info("session_started", session_id=str(session.id))
    return {"session_id": str(session.id)}


@router.post("/agent/session/end", status_code=200)
async def end_session(
    payload: SessionEnd,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="agent_session_end",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=payload.device_token,
    )
    device = await _get_approved_device(payload.device_token, db)
    result = await db.execute(
        select(WorkSession).where(
            WorkSession.id == payload.session_id,
            WorkSession.device_id == device.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"status": "not_found"}
    now = datetime.now(timezone.utc)
    session.ended_at = now
    session.duration_seconds = int((now - session.started_at).total_seconds())
    session.productivity_score = compute_session_score(session)

    # Automatically check out employee if session ends after work hours
    try:
        from app.models import Employee, AttendanceRecord
        from app.services.attendance_service import check_out
        import zoneinfo

        emp_res = await db.execute(select(Employee).where(Employee.id == device.employee_id))
        emp = emp_res.scalar_one_or_none()
        if emp:
            work_end_hr = getattr(emp, "work_end_hour", 18)
            tz_str = getattr(emp, "timezone", "UTC")
            try:
                tz = zoneinfo.ZoneInfo(tz_str)
            except Exception:
                tz = timezone.utc

            local_now = now.astimezone(tz)
            if local_now.hour >= work_end_hr:
                checkout_res = await check_out(db, device.employee_id, latitude=None, longitude=None, bypass_location=True)
                log.info("agent_shutdown_checkout_attempted", employee_id=str(device.employee_id), result=checkout_res)
    except Exception as e:
        log.warning(f"failed_to_checkout_on_agent_shutdown: {e}")

    await db.commit()
    return {"status": "closed"}


@router.post("/agent/events", response_model=BatchResponse)
async def ingest_events(
    payload: ActivityBatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        key_prefix="agent_events",
        limit=settings.AGENT_UPLOAD_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
        custom_identifier=payload.device_token,
    )
    if len(payload.events) > settings.BATCH_SIZE_LIMIT:
        raise HTTPException(status_code=400, detail=f"Batch too large (max {settings.BATCH_SIZE_LIMIT})")

    device = await _get_approved_device(payload.device_token, db)

    # ── Update device info if still pending ───────────────────────────────────
    if device.hostname in ("pending", "unknown", "", None):
        try:
            device.hostname = socket.gethostname()
        except Exception:
            device.hostname = "unknown-device"
    if device.platform in ("unknown", "", None):
        device.platform = plat.system().lower()

    # ── Resolve session ────────────────────────────────────────────────────────
    session: Optional[WorkSession] = None
    session_id: Optional[uuid.UUID] = None

    if payload.session_id:
        sess_result = await db.execute(
            select(WorkSession).where(
                WorkSession.id == payload.session_id,
                WorkSession.device_id == device.id,
                WorkSession.ended_at.is_(None),
            )
        )
        session = sess_result.scalar_one_or_none()
        if session:
            session_id = session.id

    if session is None:
        started_at = payload.events[0].timestamp if payload.events else datetime.now(timezone.utc)
        session = WorkSession(
            employee_id=device.employee_id,
            device_id=device.id,
            started_at=started_at,
        )
        db.add(session)
        await db.flush()
        session_id = session.id

    # ── Build events ───────────────────────────────────────────────────────────
    event_objects = []
    active_secs = 0
    idle_secs = 0
    prev_app = None

    for ev in payload.events:
        category = categorize_app(ev.active_app) if ev.active_app else None
        if category == "other" and ev.active_app:
            from app.services.categorizer import _smart_categories_cache, trigger_smart_categorization
            if ev.active_app in _smart_categories_cache:
                category = _smart_categories_cache[ev.active_app]
            else:
                trigger_smart_categorization(ev.active_app, ev.active_window_title)

        event_objects.append(ActivityEvent(
            device_id=device.id,
            employee_id=device.employee_id,
            session_id=session_id,
            timestamp=ev.timestamp,
            activity_type=ev.activity_type,
            active_app=ev.active_app,
            active_window_title=ev.active_window_title,
            app_category=category,
            keystrokes=ev.keystrokes,
            mouse_clicks=ev.mouse_clicks,
            mouse_distance_px=ev.mouse_distance_px,
            idle_duration_seconds=ev.idle_duration_seconds,
            sample_duration_seconds=ev.sample_duration_seconds,
        ))
        if ev.activity_type == "active":
            active_secs += ev.sample_duration_seconds
        elif ev.activity_type == "idle":
            idle_secs += ev.sample_duration_seconds
        if ev.active_app and ev.active_app != prev_app:
            session.app_switches = (session.app_switches or 0) + 1
            prev_app = ev.active_app

    db.add_all(event_objects)

    # ── Update session ─────────────────────────────────────────────────────────
    session.active_seconds = (session.active_seconds or 0) + active_secs
    session.idle_seconds = (session.idle_seconds or 0) + idle_secs
    session.productivity_score = compute_session_score(session)
    device.last_heartbeat = datetime.now(timezone.utc)

    await db.commit()

    log.debug(f"events_ingested: {len(event_objects)} events, "
              f"active={active_secs}s idle={idle_secs}s "
              f"score={session.productivity_score}")

    # ── Anomaly detection ──────────────────────────────────────────────────────
    # CRITICAL FIX: Do NOT use begin_nested() - a savepoint rollback silently
    # kills ALL anomaly inserts when any single check raises an exception.
    try:
        await check_anomalies(device, payload.events, db)
        await db.commit()
    except Exception as e:
        await db.rollback()
        log.warning(f"anomaly_check_error: {e}")

    # ── Trigger daily summary recompute in background ──────────────────────────
    # TODO(background-job): Replace asyncio.create_task with a proper job queue
    # (Celery/ARQ) for reliability. Current approach has no error tracking and
    # the task can outlive the DB session.
    try:
        from app.services.aggregator import compute_daily_summaries
        import asyncio
        asyncio.create_task(compute_daily_summaries())
    except Exception:
        pass

    # ── WebSocket broadcast ────────────────────────────────────────────────────
    try:
        if payload.events:
            latest = payload.events[-1]
            await broadcast_employee_update({
                "employee_id": str(device.employee_id),
                "activity_type": latest.activity_type,
                "active_app": latest.active_app,
                "active_window_title": latest.active_window_title,
                "idle_seconds": latest.idle_duration_seconds,
                "timestamp": latest.timestamp.isoformat(),
                "productivity_score": session.productivity_score,
                "active_seconds_today": session.active_seconds,
            })
    except Exception as e:
        log.warning(f"ws_broadcast_failed: {e}")

    return BatchResponse(
        accepted=len(event_objects),
        session_id=session_id,
        server_time=datetime.now(timezone.utc),
    )


# NOTE: _compute_score has been consolidated into app.services.scoring.compute_session_score


@router.get("/agent/stream-config/{employee_id}")
async def get_stream_config(
    employee_id: str,
    admin=Depends(require_admin_read),
):
    """Retrieve the current screen streaming configuration for an employee."""
    return stream_manager.get_stream_config(employee_id)


@router.put("/agent/stream-config/{employee_id}")
async def update_stream_config(
    employee_id: str,
    payload: StreamConfigUpdate,
    admin=Depends(require_admin_write),
):
    """Update screen streaming configurations (enabled, fps, quality) for an employee."""
    fps = payload.fps if payload.fps is not None else 24.0
    quality = payload.quality if payload.quality is not None else 50
    await stream_manager.set_stream_config(
        employee_id=employee_id,
        enabled=payload.enabled,
        fps=fps,
        quality=quality,
    )
    return {"status": "success", "config": stream_manager.get_stream_config(employee_id)}

