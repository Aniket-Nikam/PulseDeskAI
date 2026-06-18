from datetime import datetime, date, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.models import (
    Employee, Device, DeviceStatus,
    ActivityEvent, AnomalyLog, DailySummary, WorkSession, Screenshot,
    ActivityType
)
from app.api.v1.routes.auth import get_current_admin
from app.core.logging import get_logger
from app.services.scoring import compute_score_from_events

router = APIRouter(prefix="/employee/portal", tags=["employee-portal"])
log = get_logger("employee_portal")

def require_employee(user = Depends(get_current_admin)):
    # Check if the role is employee
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role_val != "employee":
        raise HTTPException(status_code=403, detail="Only employees can access the self-monitoring portal.")
    return user

@router.get("/dashboard")
async def get_employee_dashboard(
    user = Depends(require_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated dashboard stats for the logged-in employee.
    """
    emp_id = user.id

    # Fetch last 30 daily summaries
    summaries_result = await db.execute(
        select(DailySummary)
        .where(DailySummary.employee_id == emp_id)
        .order_by(DailySummary.date.desc())
        .limit(30)
    )
    summaries = summaries_result.scalars().all()

    # Calculate average productivity score and sums
    total_active_seconds = 0
    total_idle_seconds = 0
    total_focus_seconds = 0
    total_tracked_seconds = 0
    productivity_sum = 0.0
    anomalies_count = 0

    for s in summaries:
        total_active_seconds += s.active_seconds
        total_idle_seconds += s.idle_seconds
        total_focus_seconds += getattr(s, "focus_seconds", 0) or 0
        total_tracked_seconds += s.total_tracked_seconds
        productivity_sum += s.productivity_score
        anomalies_count += s.anomaly_count

    avg_productivity = (productivity_sum / len(summaries)) if summaries else 0.0

    # Fetch top app / top category from summaries
    top_app = None
    top_category = None
    if summaries:
        # Simple frequency check
        apps = [s.top_app for s in summaries if s.top_app]
        categories = [s.top_category for s in summaries if s.top_category]
        if apps:
            top_app = max(set(apps), key=apps.count)
        if categories:
            top_category = max(set(categories), key=categories.count)

    # Format daily summaries for trend chart
    chart_data = [
        {
            "date": s.date.strftime("%Y-%m-%d") if s.date else "",
            "active_hours": round(s.active_seconds / 3600, 2),
            "idle_hours": round(s.idle_seconds / 3600, 2),
            "productivity_score": round(s.productivity_score * 100, 1),
        }
        for s in reversed(summaries)
    ]

    return {
        "employee": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "job_title": getattr(user, "job_title", ""),
            "timezone": getattr(user, "timezone", "UTC"),
        },
        "stats": {
            "total_active_hours": round(total_active_seconds / 3600, 2),
            "total_idle_hours": round(total_idle_seconds / 3600, 2),
            "total_focus_hours": round(total_focus_seconds / 3600, 2),
            "total_tracked_hours": round(total_tracked_seconds / 3600, 2),
            "avg_productivity_score": round(avg_productivity * 100, 1),
            "total_anomalies": anomalies_count,
            "top_app": top_app,
            "top_category": top_category,
        },
        "chart_data": chart_data
    }

@router.get("/timeline")
async def get_employee_timeline(
    date_str: Optional[str] = Query(None, alias="date"),
    user = Depends(require_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Get timeline blocks for the logged-in employee on a given date.
    """
    from zoneinfo import ZoneInfo
    
    target_date = date.today()
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD")

    ist_tz = ZoneInfo("Asia/Kolkata")
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=ist_tz)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(ActivityEvent).where(
            ActivityEvent.employee_id == user.id,
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
        "date": target_date.isoformat(),
        "blocks": blocks,
        "total_tracked_seconds": sum(e.sample_duration_seconds for e in events),
        "active_seconds": active,
        "idle_seconds": idle,
        "productivity_score": round(score * 100, 1)
    }

@router.get("/consent")
async def get_employee_consent(user = Depends(require_employee)):
    """
    Get current employee GDPR consent status.
    """
    return {
        "employee_id": str(user.id),
        "employee_name": user.full_name,
        "consent_given": user.consent_given_at is not None and user.consent_revoked_at is None,
        "consent_given_at": user.consent_given_at.isoformat() if user.consent_given_at else None,
        "consent_revoked_at": user.consent_revoked_at.isoformat() if user.consent_revoked_at else None,
    }

@router.post("/consent")
async def toggle_employee_consent(
    payload: dict,
    user = Depends(require_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggles GDPR consent status. If revoked, active tracking is suspended on all devices.
    """
    consent_given = payload.get("consent_given", False)
    now = datetime.now(timezone.utc)

    # Fetch employee to update
    emp_result = await db.execute(select(Employee).where(Employee.id == user.id))
    employee = emp_result.scalar_one()

    # Update devices
    dev_result = await db.execute(select(Device).where(Device.employee_id == user.id))
    devices = dev_result.scalars().all()

    if consent_given:
        employee.consent_given_at = now
        employee.consent_revoked_at = None
        for dev in devices:
            dev.monitoring_consent_given = True
            if dev.status == DeviceStatus.suspended:
                dev.status = DeviceStatus.approved
        log.info("consent_given_self", employee_id=str(user.id))
    else:
        employee.consent_revoked_at = now
        for dev in devices:
            dev.monitoring_consent_given = False
            dev.status = DeviceStatus.suspended
        log.warning("consent_revoked_self", employee_id=str(user.id))

    await db.commit()

    return {
        "consent_given": consent_given,
        "consent_given_at": employee.consent_given_at.isoformat() if employee.consent_given_at else None,
        "consent_revoked_at": employee.consent_revoked_at.isoformat() if employee.consent_revoked_at else None,
        "message": "Consent updated successfully. Devices suspended/approved."
    }

@router.get("/export")
async def export_my_data(
    user = Depends(require_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    GDPR Article 15: Export all telemetry data stored for the logged-in employee.
    """
    emp_id = user.id

    # Fetch all events (last 10k)
    events_res = await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.employee_id == emp_id)
        .order_by(ActivityEvent.timestamp.desc())
        .limit(10000)
    )
    events = events_res.scalars().all()

    # Fetch daily summaries
    summaries_res = await db.execute(
        select(DailySummary)
        .where(DailySummary.employee_id == emp_id)
        .order_by(DailySummary.date.desc())
    )
    summaries = summaries_res.scalars().all()

    # Fetch anomaly logs
    anomalies_res = await db.execute(
        select(AnomalyLog)
        .where(AnomalyLog.employee_id == emp_id)
        .order_by(AnomalyLog.detected_at.desc())
    )
    anomalies = anomalies_res.scalars().all()

    # Fetch work sessions
    sessions_res = await db.execute(
        select(WorkSession)
        .where(WorkSession.employee_id == emp_id)
        .order_by(WorkSession.started_at.desc())
    )
    sessions = sessions_res.scalars().all()

    return {
        "employee_profile": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "job_title": getattr(user, "job_title", ""),
            "timezone": getattr(user, "timezone", "UTC"),
            "consent_given_at": user.consent_given_at.isoformat() if user.consent_given_at else None,
            "consent_revoked_at": user.consent_revoked_at.isoformat() if user.consent_revoked_at else None,
        },
        "daily_summaries": [
            {
                "date": s.date.strftime("%Y-%m-%d"),
                "total_tracked_seconds": s.total_tracked_seconds,
                "active_seconds": s.active_seconds,
                "idle_seconds": s.idle_seconds,
                "productivity_score": s.productivity_score,
                "anomaly_count": s.anomaly_count,
            }
            for s in summaries
        ],
        "work_sessions": [
            {
                "started_at": ws.started_at.isoformat(),
                "ended_at": ws.ended_at.isoformat() if ws.ended_at else None,
                "duration_seconds": ws.duration_seconds,
                "active_seconds": ws.active_seconds,
                "idle_seconds": ws.idle_seconds,
                "productivity_score": ws.productivity_score,
            }
            for ws in sessions
        ],
        "anomalies": [
            {
                "detected_at": a.detected_at.isoformat(),
                "anomaly_type": a.anomaly_type.value if hasattr(a.anomaly_type, "value") else str(a.anomaly_type),
                "description": a.description,
            }
            for a in anomalies
        ],
        "activity_events_sample": [
            {
                "timestamp": e.timestamp.isoformat(),
                "activity_type": e.activity_type.value if hasattr(e.activity_type, "value") else str(e.activity_type),
                "active_app": e.active_app,
                "active_window_title": e.active_window_title,
                "app_category": e.app_category,
            }
            for e in events
        ]
    }

@router.delete("/erase")
async def erase_my_data(
    user = Depends(require_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    GDPR Article 17: Right to Erasure. Permanently delete all tracking events and metadata.
    """
    emp_id = user.id

    # 1. Delete screenshots
    await db.execute(delete(Screenshot).where(Screenshot.employee_id == emp_id))
    # 2. Delete anomalies
    await db.execute(delete(AnomalyLog).where(AnomalyLog.employee_id == emp_id))
    # 3. Delete activity events
    await db.execute(delete(ActivityEvent).where(ActivityEvent.employee_id == emp_id))
    # 4. Delete daily summaries
    await db.execute(delete(DailySummary).where(DailySummary.employee_id == emp_id))
    # 5. Delete work sessions
    await db.execute(delete(WorkSession).where(WorkSession.employee_id == emp_id))

    # Revoke consent
    employee = await db.get(Employee, emp_id)
    employee.consent_revoked_at = datetime.now(timezone.utc)

    # Suspend devices
    dev_result = await db.execute(select(Device).where(Device.employee_id == emp_id))
    devices = dev_result.scalars().all()
    for dev in devices:
        dev.monitoring_consent_given = False
        dev.status = DeviceStatus.suspended

    await db.commit()
    log.warning("gdpr_erasure_triggered_by_employee", employee_id=str(emp_id))

    return {
        "status": "success",
        "message": "All activity data has been permanently erased. Devices suspended."
    }
