"""
PulseDesk Analytics Routes — Production
All endpoints use live data with daily summary as cache layer.
Scoring consolidated into app.services.scoring.
"""

import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models import (
    ActivityEvent, WorkSession, DailySummary,
    Employee, Department, Device, DeviceStatus, AnomalyLog, ActivityType,
)
from app.services.online_tracker import is_device_online, get_employee_last_event
from app.services.categorizer import categorize_app, is_productive_category
from app.services.scoring import compute_score_from_events
from app.services import analytics_service
from app.schemas import PaginatedResponse, AnomalyOut
from app.core.config import settings
from app.core.logging import get_logger
from app.core.audit import log_admin_action
from app.api.v1.routes.auth import require_admin_read, require_admin_write

router = APIRouter(prefix="/analytics", tags=["analytics"])
log = get_logger("analytics")

# NOTE: _score_from_events has been consolidated into app.services.scoring.compute_score_from_events


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/overview")
async def get_live_overview(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active == True)
        .order_by(Employee.full_name)
    )
    rows = result.all()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []

    for employee, dept_name in rows:
        last_event = await get_employee_last_event(employee.id, db)

        today_active_result = await db.execute(
            select(func.sum(ActivityEvent.sample_duration_seconds)).where(
                ActivityEvent.employee_id == employee.id,
                ActivityEvent.activity_type == ActivityType.active,
                ActivityEvent.timestamp >= today_start,
            )
        )
        today_active = int(today_active_result.scalar() or 0)

        today_events_result = await db.execute(
            select(ActivityEvent).where(
                ActivityEvent.employee_id == employee.id,
                ActivityEvent.timestamp >= today_start,
            ).limit(500)
        )
        today_events = today_events_result.scalars().all()
        prod_score = compute_score_from_events(today_events) if today_events else None

        device_result = await db.execute(
            select(Device).where(
                Device.employee_id == employee.id,
                Device.status == DeviceStatus.approved,
            ).order_by(Device.last_heartbeat.desc()).limit(1)
        )
        device = device_result.scalar_one_or_none()

        session_result = await db.execute(
            select(WorkSession).where(
                WorkSession.employee_id == employee.id,
                WorkSession.ended_at.is_(None),
            ).order_by(WorkSession.started_at.desc()).limit(1)
        )
        session = session_result.scalar_one_or_none()

        # Device info for display
        device_count_result = await db.execute(
            select(func.count(Device.id)).where(
                Device.employee_id == employee.id,
                Device.status == DeviceStatus.approved,
            )
        )
        device_count = device_count_result.scalar() or 0

        out.append({
            "employee_id": str(employee.id),
            "employee_name": employee.full_name,
            "department_name": dept_name,
            "is_online": is_device_online(device) if device else False,
            "activity_type": last_event.activity_type if last_event else None,
            "active_app": last_event.active_app if last_event else None,
            "active_window_title": last_event.active_window_title if last_event else None,
            "idle_seconds": last_event.idle_duration_seconds if last_event else 0,
            "session_started_at": session.started_at.isoformat() if session else None,
            "today_active_seconds": today_active,
            "today_productivity_score": prod_score,
            "last_seen": last_event.timestamp.isoformat() if last_event else None,
            "device_count": device_count,
        })

    return out


# ── Leaderboard (single endpoint, no N+1 queries) ─────────────────────────────

@router.get("/leaderboard")
async def get_leaderboard(
    days: int = Query(default=7, ge=1, le=30),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns ranked leaderboard in a single DB pass.
    Uses daily summaries if available, falls back to live event data.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active == True)
    )
    employees = emp_result.all()

    entries = []

    for employee, dept_name in employees:
        # Try daily summaries first
        summ_result = await db.execute(
            select(DailySummary).where(
                DailySummary.employee_id == employee.id,
                DailySummary.date >= since,
            ).order_by(DailySummary.date.desc())
        )
        summaries = summ_result.scalars().all()

        if summaries:
            avg_score = round(sum(s.productivity_score for s in summaries) / len(summaries), 1)
            total_active = sum(s.active_seconds for s in summaries)
            focus = sum(s.focus_sessions for s in summaries)

            # Streak
            sorted_s = sorted(summaries, key=lambda x: x.date, reverse=True)
            streak = 0
            for s in sorted_s:
                if s.productivity_score >= 60:
                    streak += 1
                else:
                    break

            # Trend
            half = max(len(summaries) // 2, 1)
            recent_avg = sum(s.productivity_score for s in summaries[:half]) / half
            older_avg = sum(s.productivity_score for s in summaries[half:]) / max(len(summaries[half:]), 1)
            trend = "up" if recent_avg > older_avg + 5 else "down" if recent_avg < older_avg - 5 else "same"
            days_data = len(summaries)

        else:
            # Fall back to today's live events
            ev_result = await db.execute(
                select(ActivityEvent).where(
                    ActivityEvent.employee_id == employee.id,
                    ActivityEvent.timestamp >= today_start,
                ).limit(500)
            )
            events = ev_result.scalars().all()
            if not events:
                continue

            avg_score = compute_score_from_events(events)
            total_active = sum(e.sample_duration_seconds for e in events if e.activity_type == ActivityType.active)
            focus = 0
            streak = 1 if avg_score >= 60 else 0
            trend = "same"
            days_data = 1

        if avg_score == 0 and total_active == 0:
            continue

        entries.append({
            "employee_id": str(employee.id),
            "employee_name": employee.full_name,
            "department_name": dept_name,
            "avg_score": avg_score,
            "total_active_seconds": total_active,
            "focus_sessions": focus,
            "streak_days": streak,
            "trend": trend,
            "days_with_data": days_data,
            "rank": 0,
        })

    entries.sort(key=lambda x: -x["avg_score"])
    for i, e in enumerate(entries):
        e["rank"] = i + 1

    return entries


# ── Timeline ──────────────────────────────────────────────────────────────────
from zoneinfo import ZoneInfo

@router.get("/timeline/{employee_id}")
async def get_timeline(
    employee_id: uuid.UUID,
    date_str: str = Query(..., alias="date"),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD")

    ist_tz = ZoneInfo("Asia/Kolkata")
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=ist_tz)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(ActivityEvent).where(
            ActivityEvent.employee_id == employee_id,
            ActivityEvent.timestamp >= day_start,
            ActivityEvent.timestamp < day_end,
        ).order_by(ActivityEvent.timestamp)
    )
    events = result.scalars().all()

    blocks = [
        {
            "start": e.timestamp.astimezone(ist_tz).isoformat(),
            "end": (e.timestamp.astimezone(ist_tz) + timedelta(seconds=e.sample_duration_seconds)).isoformat(),
            "activity_type": e.activity_type,
            "app": e.active_app,
            "app_category": e.app_category,
        }
        for e in events
    ]

    active = sum(e.sample_duration_seconds for e in events if e.activity_type == ActivityType.active)
    idle = sum(e.sample_duration_seconds for e in events if e.activity_type == ActivityType.idle)
    score = compute_score_from_events(events)

    return {
        "employee_id": str(employee_id),
        "date": date_str,
        "blocks": blocks,
        "total_tracked_seconds": sum(e.sample_duration_seconds for e in events),
        "active_seconds": active,
        "idle_seconds": idle,
        "productivity_score": score,
    }


# ── Heatmap ───────────────────────────────────────────────────────────────────

@router.get("/heatmap/{employee_id}")
async def get_heatmap(
    employee_id: uuid.UUID,
    date_str: str = Query(..., alias="date"),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    ist_tz = ZoneInfo("Asia/Kolkata")
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=ist_tz)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(ActivityEvent).where(
            ActivityEvent.employee_id == employee_id,
            ActivityEvent.timestamp >= day_start,
            ActivityEvent.timestamp < day_end,
            ActivityEvent.activity_type == ActivityType.active,
        )
    )
    events = result.scalars().all()

    hourly: dict = defaultdict(int)
    for e in events:
        local_time = e.timestamp.astimezone(ist_tz)
        hourly[local_time.hour] += e.sample_duration_seconds

    return {
        "employee_id": str(employee_id),
        "date": date_str,
        "hours": {str(h): hourly.get(h, 0) for h in range(24)},
    }


# ── App Usage ─────────────────────────────────────────────────────────────────

@router.get("/app-usage/{employee_id}")
async def get_app_usage(
    employee_id: uuid.UUID,
    date_str: str = Query(..., alias="date"),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    ist_tz = ZoneInfo("Asia/Kolkata")
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=ist_tz)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(ActivityEvent).where(
            ActivityEvent.employee_id == employee_id,
            ActivityEvent.timestamp >= day_start,
            ActivityEvent.timestamp < day_end,
            ActivityEvent.active_app.isnot(None),
        )
    )
    events = result.scalars().all()

    app_time: dict = defaultdict(int)
    app_cat: dict = {}
    for e in events:
        app_time[e.active_app] += e.sample_duration_seconds
        if e.app_category:
            app_cat[e.active_app] = e.app_category

    total = max(sum(app_time.values()), 1)
    stats = [
        {
            "app_name": app,
            "app_category": app_cat.get(app, "other"),
            "total_seconds": secs,
            "percentage": round(secs / total * 100, 1),
        }
        for app, secs in sorted(app_time.items(), key=lambda x: -x[1])
    ]
    return stats[:20]


# ── Summaries (14-day history) ─────────────────────────────────────────────────

@router.get("/summaries/{employee_id}")
async def get_summaries(
    employee_id: uuid.UUID,
    days: int = Query(default=14, ge=1, le=30),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(DailySummary).where(
            DailySummary.employee_id == employee_id,
            DailySummary.date >= since,
        ).order_by(DailySummary.date.desc())
    )
    summaries = result.scalars().all()

    # If no historical summaries, compute today live
    if not summaries:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        ev_result = await db.execute(
            select(ActivityEvent).where(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.timestamp >= today_start,
            )
        )
        events = ev_result.scalars().all()
        if not events:
            return []
        score = compute_score_from_events(events)
        active = sum(e.sample_duration_seconds for e in events if e.activity_type == ActivityType.active)
        return [{
            "id": str(uuid.uuid4()),
            "employee_id": str(employee_id),
            "date": today_start.isoformat(),
            "total_tracked_seconds": sum(e.sample_duration_seconds for e in events),
            "active_seconds": active,
            "idle_seconds": sum(e.sample_duration_seconds for e in events if e.activity_type == ActivityType.idle),
            "focus_seconds": 0,
            "productivity_score": score,
            "focus_sessions": 0,
            "app_switches": 0,
            "top_app": None,
            "top_category": None,
            "anomaly_count": 0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }]

    return [{
        "id": str(s.id),
        "employee_id": str(s.employee_id),
        "date": s.date.isoformat(),
        "total_tracked_seconds": s.total_tracked_seconds,
        "active_seconds": s.active_seconds,
        "idle_seconds": s.idle_seconds,
        "focus_seconds": s.focus_seconds,
        "productivity_score": s.productivity_score,
        "focus_sessions": s.focus_sessions,
        "app_switches": s.app_switches,
        "top_app": s.top_app,
        "top_category": s.top_category,
        "anomaly_count": s.anomaly_count,
        "computed_at": s.computed_at.isoformat() if s.computed_at else None,
    } for s in summaries]


# ── Department comparison ─────────────────────────────────────────────────────
# TODO(performance): This endpoint has N+1 query issues. For each department,
# it loops over employees and fires separate queries. Should be refactored to
# use aggregated subqueries or cached daily summaries.

@router.get("/department-comparison")
async def get_dept_comparison(
    date_str: str = Query(default=None, alias="date"),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    target_date = date.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    dept_result = await db.execute(select(Department))
    departments = dept_result.scalars().all()

    out = []
    for dept in departments:
        emp_result = await db.execute(
            select(Employee).where(
                Employee.department_id == dept.id,
                Employee.is_active == True,
            )
        )
        employees = emp_result.scalars().all()
        if not employees:
            out.append({
                "department_id": str(dept.id),
                "department_name": dept.name,
                "employee_count": 0,
                "online_count": 0,
                "avg_productivity_score": 0.0,
                "avg_active_seconds": 0,
            })
            continue

        scores, actives, online_count = [], [], 0

        for emp in employees:
            ev_result = await db.execute(
                select(ActivityEvent).where(
                    ActivityEvent.employee_id == emp.id,
                    ActivityEvent.timestamp >= day_start,
                    ActivityEvent.timestamp < day_end,
                ).limit(300)
            )
            events = ev_result.scalars().all()
            if events:
                scores.append(compute_score_from_events(events))
                actives.append(sum(e.sample_duration_seconds for e in events if e.activity_type == ActivityType.active))

            dev_result = await db.execute(
                select(Device).where(
                    Device.employee_id == emp.id,
                    Device.status == DeviceStatus.approved,
                ).order_by(Device.last_heartbeat.desc()).limit(1)
            )
            dev = dev_result.scalar_one_or_none()
            if is_device_online(dev):
                online_count += 1

        out.append({
            "department_id": str(dept.id),
            "department_name": dept.name,
            "employee_count": len(employees),
            "online_count": online_count,
            "avg_productivity_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "avg_active_seconds": int(sum(actives) / len(actives)) if actives else 0,
            "avg_focus_sessions": 0.0,
            "avg_app_switches": 0.0,
        })

    return sorted(out, key=lambda x: -x["avg_productivity_score"])


# ── Anomalies ─────────────────────────────────────────────────────────────────

@router.get("/anomalies")
async def get_anomalies(
    is_reviewed: Optional[bool] = Query(default=None),
    employee_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=50, le=200),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    q = select(AnomalyLog, Employee.full_name.label("emp_name")).outerjoin(
        Employee, AnomalyLog.employee_id == Employee.id
    )
    if is_reviewed is not None:
        q = q.where(AnomalyLog.is_reviewed == is_reviewed)
    if employee_id:
        q = q.where(AnomalyLog.employee_id == employee_id)
    q = q.order_by(AnomalyLog.detected_at.desc()).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    return [{
        "id": str(a.id),
        "employee_id": str(a.employee_id),
        "employee_name": name,
        "device_id": str(a.device_id),
        "anomaly_type": a.anomaly_type.value if hasattr(a.anomaly_type, "value") else str(a.anomaly_type),
        "detected_at": a.detected_at.isoformat(),
        "description": a.description,
        "metadata": a.event_metadata,
        "is_reviewed": a.is_reviewed,
        "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
    } for a, name in rows]


@router.patch("/anomalies/{anomaly_id}/review")
async def review_anomaly(
    anomaly_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AnomalyLog).where(AnomalyLog.id == anomaly_id))
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    anomaly.is_reviewed = True
    anomaly.reviewed_by = admin.id
    anomaly.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    log_admin_action("anomaly_reviewed", admin_id=str(admin.id), anomaly_id=str(anomaly_id))
    return {"status": "reviewed"}


@router.post("/recompute-summaries")
async def recompute(admin=Depends(require_admin_write)):
    from app.services.aggregator import compute_daily_summaries
    count = await compute_daily_summaries()
    log_admin_action("daily_summaries_recomputed", admin_id=str(admin.id), employees_computed=count)
    return {"status": "done", "employees_computed": count}
