"""
GDPR Consent Management

Endpoints for:
- Agent to submit employee monitoring consent
- Admin to check consent status
- Employee data export (GDPR Article 15 — Right of Access)
- Employee data deletion (GDPR Article 17 — Right to Erasure)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.models import (
    Employee, Device, DeviceStatus,
    ActivityEvent, AnomalyLog, DailySummary, WorkSession, Screenshot,
)
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.logging import get_logger
from app.core.audit import log_admin_action
from app.core.agent_auth import verify_agent_request_signature
from app.core.security import device_token_lookup_values
from pydantic import BaseModel

router = APIRouter(prefix="/consent", tags=["gdpr-consent"])
log = get_logger("consent")


class ConsentPayload(BaseModel):
    device_token: str
    consent_given: bool


class ConsentStatus(BaseModel):
    employee_id: str
    employee_name: str
    consent_given: bool
    consent_given_at: str | None
    consent_revoked_at: str | None


# ── Agent-facing: submit consent ──────────────────────────────────────────────

@router.post("/submit")
async def submit_consent(
    payload: ConsentPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the agent when the employee accepts or declines monitoring.
    If declined, the device is suspended and the agent should stop tracking.
    """
    await verify_agent_request_signature(request, payload.device_token)

    result = await db.execute(
        select(Device).where(
            Device.device_token.in_(device_token_lookup_values(payload.device_token)),
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Unknown device")

    emp_result = await db.execute(select(Employee).where(Employee.id == device.employee_id))
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    now = datetime.now(timezone.utc)

    if payload.consent_given:
        device.monitoring_consent_given = True
        employee.consent_given_at = now
        employee.consent_revoked_at = None
        log.info("consent_given", employee_id=str(employee.id), device_id=str(device.id))
    else:
        device.monitoring_consent_given = False
        device.status = DeviceStatus.suspended
        employee.consent_revoked_at = now
        log.warning("consent_revoked", employee_id=str(employee.id), device_id=str(device.id))

    await db.commit()

    return {
        "status": "accepted" if payload.consent_given else "declined",
        "employee_id": str(employee.id),
        "monitoring_active": payload.consent_given,
        "message": (
            "Monitoring consent recorded. Activity tracking is now active."
            if payload.consent_given
            else "Consent declined. Monitoring has been suspended on this device."
        ),
    }


# ── Admin-facing: check consent status ────────────────────────────────────────

@router.get("/status")
async def get_consent_status(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Get consent status for all employees."""
    result = await db.execute(select(Employee).where(Employee.is_active))
    employees = result.scalars().all()

    statuses = []
    for emp in employees:
        statuses.append({
            "employee_id": str(emp.id),
            "employee_name": emp.full_name,
            "email": emp.email,
            "consent_given": emp.consent_given_at is not None and emp.consent_revoked_at is None,
            "consent_given_at": emp.consent_given_at.isoformat() if emp.consent_given_at else None,
            "consent_revoked_at": emp.consent_revoked_at.isoformat() if emp.consent_revoked_at else None,
        })

    return {
        "employees": statuses,
        "total": len(statuses),
        "consented": sum(1 for s in statuses if s["consent_given"]),
        "pending": sum(1 for s in statuses if not s["consent_given"]),
    }


# ── GDPR Article 15: Data Export ──────────────────────────────────────────────

@router.get("/export/{employee_id}")
async def export_employee_data(
    employee_id: uuid.UUID,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all data collected for an employee (GDPR Right of Access).
    Returns a JSON dump of all activity events, anomalies, and summaries.
    """
    emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Activity events (last 90 days to keep response reasonable)
    events_result = await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.employee_id == employee_id)
        .order_by(ActivityEvent.timestamp.desc())
        .limit(10000)
    )
    events = events_result.scalars().all()

    # Anomalies
    anomalies_result = await db.execute(
        select(AnomalyLog)
        .where(AnomalyLog.employee_id == employee_id)
        .order_by(AnomalyLog.detected_at.desc())
    )
    anomalies = anomalies_result.scalars().all()

    # Daily summaries
    summaries_result = await db.execute(
        select(DailySummary)
        .where(DailySummary.employee_id == employee_id)
        .order_by(DailySummary.date.desc())
    )
    summaries = summaries_result.scalars().all()

    log_admin_action("employee_data_exported", admin_id=str(admin.id), employee_id=str(employee_id))

    return {
        "employee": {
            "id": str(employee.id),
            "email": employee.email,
            "full_name": employee.full_name,
            "consent_given_at": employee.consent_given_at.isoformat() if employee.consent_given_at else None,
        },
        "activity_events_count": len(events),
        "activity_events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "active_app": e.active_app,
                "active_window_title": e.active_window_title,
                "activity_type": e.activity_type.value if hasattr(e.activity_type, 'value') else str(e.activity_type),
                "category": e.app_category,
            }
            for e in events
        ],
        "anomalies_count": len(anomalies),
        "anomalies": [
            {
                "detected_at": a.detected_at.isoformat(),
                "type": a.anomaly_type.value if hasattr(a.anomaly_type, 'value') else str(a.anomaly_type),
                "description": a.description,
            }
            for a in anomalies
        ],
        "daily_summaries_count": len(summaries),
        "daily_summaries": [
            {
                "date": str(s.date),
                "active_seconds": s.active_seconds,
                "productivity_score": s.productivity_score,
                "focus_sessions": s.focus_sessions,
            }
            for s in summaries
        ],
    }


# ── GDPR Article 17: Data Deletion ───────────────────────────────────────────

@router.delete("/erase/{employee_id}")
async def erase_employee_data(
    employee_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete all monitoring data for an employee (GDPR Right to Erasure).
    Preserves the employee record itself but removes all activity data.
    """
    emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Delete all activity data (order matters due to FK constraints)
    deleted_screenshots = await db.execute(
        delete(Screenshot).where(Screenshot.employee_id == employee_id)
    )
    deleted_anomalies = await db.execute(
        delete(AnomalyLog).where(AnomalyLog.employee_id == employee_id)
    )
    deleted_events = await db.execute(
        delete(ActivityEvent).where(ActivityEvent.employee_id == employee_id)
    )
    deleted_summaries = await db.execute(
        delete(DailySummary).where(DailySummary.employee_id == employee_id)
    )
    deleted_sessions = await db.execute(
        delete(WorkSession).where(WorkSession.employee_id == employee_id)
    )

    # Mark consent as revoked
    employee.consent_revoked_at = datetime.now(timezone.utc)

    await db.commit()

    counts = {
        "activity_events": deleted_events.rowcount,
        "anomalies": deleted_anomalies.rowcount,
        "daily_summaries": deleted_summaries.rowcount,
        "screenshots": deleted_screenshots.rowcount,
        "work_sessions": deleted_sessions.rowcount,
    }

    log.warning("employee_data_erased",
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                **counts)

    log_admin_action("employee_data_erased",
                     admin_id=str(admin.id),
                     employee_id=str(employee_id),
                     **counts)

    return {
        "status": "erased",
        "employee_id": str(employee_id),
        "employee_name": employee.full_name,
        "deleted": counts,
        "message": f"All monitoring data for {employee.full_name} has been permanently deleted.",
    }
