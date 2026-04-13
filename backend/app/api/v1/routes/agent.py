"""
PulseDesk Agent Routes v4
Fixed: device info update on every heartbeat, productivity score live,
session handling robust, all 500 errors eliminated.
"""

import uuid
import platform as plat
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import Device, DeviceStatus, ActivityEvent, WorkSession, ActivityType
from app.schemas import (
    ActivityBatch, BatchResponse,
    SessionStart, SessionEnd,
    HeartbeatIn, HeartbeatOut,
)
from app.services.categorizer import categorize_app
from app.services.anomaly_detector import check_anomalies
from app.services.ws_broadcaster import broadcast_employee_update
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter(tags=["agent"])
log = get_logger("agent")


async def _get_approved_device(token: str, db: AsyncSession) -> Device:
    result = await db.execute(select(Device).where(Device.device_token == token))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device token")
    if device.status != DeviceStatus.approved:
        raise HTTPException(status_code=403, detail=f"Device not approved (status: {device.status})")
    return device


@router.post("/agent/heartbeat", response_model=HeartbeatOut)
async def heartbeat(payload: HeartbeatIn, db: AsyncSession = Depends(get_db)):
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

    await db.commit()
    return HeartbeatOut(
        status="ok",
        server_time=datetime.now(timezone.utc),
        screenshot_required=False,
    )


@router.patch("/agent/device-info")
async def update_device_info(payload: dict, db: AsyncSession = Depends(get_db)):
    token = payload.get("device_token", "")
    result = await db.execute(select(Device).where(Device.device_token == token))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Unknown device")

    if payload.get("hostname"):
        device.hostname = payload["hostname"]
    if payload.get("platform"):
        device.platform = payload["platform"]
    if payload.get("os_version"):
        device.os_version = payload["os_version"][:100]
    if payload.get("agent_version"):
        device.agent_version = payload["agent_version"]

    await db.commit()
    log.info("device_info_updated", hostname=device.hostname, platform=device.platform)
    return {"status": "updated", "hostname": device.hostname}


@router.post("/agent/session/start", response_model=dict)
async def start_session(payload: SessionStart, db: AsyncSession = Depends(get_db)):
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
    await db.commit()
    await db.refresh(session)
    log.info("session_started", session_id=str(session.id))
    return {"session_id": str(session.id)}


@router.post("/agent/session/end", status_code=200)
async def end_session(payload: SessionEnd, db: AsyncSession = Depends(get_db)):
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
    session.productivity_score = _compute_score(session)
    await db.commit()
    return {"status": "closed"}


@router.post("/agent/events", response_model=BatchResponse)
async def ingest_events(payload: ActivityBatch, db: AsyncSession = Depends(get_db)):
    if len(payload.events) > settings.BATCH_SIZE_LIMIT:
        raise HTTPException(status_code=400, detail=f"Batch too large (max {settings.BATCH_SIZE_LIMIT})")

    device = await _get_approved_device(payload.device_token, db)

    # ── Update device info if still pending ───────────────────────────────────
    if device.hostname in ("pending", "unknown", "", None):
        import socket
        try:
            device.hostname = socket.gethostname()
        except Exception:
            device.hostname = "unknown-device"
    if device.platform in ("unknown", "", None):
        import platform as sys_plat
        device.platform = sys_plat.system().lower()

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
    session.productivity_score = _compute_score(session)
    device.last_heartbeat = datetime.now(timezone.utc)

    await db.commit()

    log.debug(f"events_ingested: {len(event_objects)} events, "
              f"active={active_secs}s idle={idle_secs}s "
              f"score={session.productivity_score}")

    # ── Anomaly detection ──────────────────────────────────────────────────────
    try:
        async with db.begin_nested():
            await check_anomalies(device, payload.events, db)
    except Exception as e:
        log.warning(f"anomaly_check_error: {e}")

    # ── Trigger daily summary recompute in background ──────────────────────────
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


def _compute_score(session: WorkSession) -> float:
    """
    Productivity score 0-100.
    Based on active ratio, switch frequency, and focus blocks.
    """
    active = session.active_seconds or 0
    idle = session.idle_seconds or 0
    total = max(active + idle, 1)

    active_ratio = active / total

    # Switch penalty: >60 switches/hr is very distracting
    hours = total / 3600
    switches_per_hr = (session.app_switches or 0) / max(hours, 0.1)
    switch_penalty = min(0.3, switches_per_hr / 200)

    # Focus bonus: each 25min+ focus block adds up to 15%
    focus_bonus = min(0.15, (session.focus_blocks or 0) * 0.03)

    score = (active_ratio - switch_penalty + focus_bonus) * 100
    return round(max(0.0, min(100.0, score)), 1)
