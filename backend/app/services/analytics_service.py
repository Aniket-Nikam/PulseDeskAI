"""
PulseDesk Analytics Service Layer

Extracts business logic and complex multi-query aggregation from route handlers.
Fixes N+1 issue in department comparison.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityEvent, WorkSession, DailySummary,
    Employee, Department, Device, DeviceStatus, AnomalyLog, ActivityType,
)
from app.schemas import (
    EmployeeStatusOut, DepartmentComparisonRow, AnomalyOut
)
from app.services.online_tracker import is_device_online, get_employee_last_event
from app.services.scoring import compute_score_from_events
from app.core.pagination import paginate_query, PaginatedResult
from app.core.exceptions import NotFoundError


# ─── Live Overview ────────────────────────────────────────────────────────────

async def get_live_overview(db: AsyncSession) -> List[EmployeeStatusOut]:
    result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active)
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

        device_count_result = await db.execute(
            select(func.count(Device.id)).where(
                Device.employee_id == employee.id,
                Device.status == DeviceStatus.approved,
            )
        )
        device_count = device_count_result.scalar() or 0

        out.append(EmployeeStatusOut(
            employee_id=employee.id,
            employee_name=employee.full_name,
            department_name=dept_name,
            is_online=is_device_online(device) if device else False,
            activity_type=last_event.activity_type if last_event else None,
            active_app=last_event.active_app if last_event else None,
            active_window_title=last_event.active_window_title if last_event else None,
            idle_seconds=last_event.idle_duration_seconds if last_event else 0,
            session_started_at=session.started_at if session else None,
            today_active_seconds=today_active,
            today_productivity_score=prod_score,
            last_seen=last_event.timestamp if last_event else None,
            device_count=device_count,
        ))

    return out


# ─── Leaderboard ──────────────────────────────────────────────────────────────

async def get_leaderboard(days: int, db: AsyncSession) -> List[Dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active)
    )
    employees = emp_result.all()

    entries = []

    for employee, dept_name in employees:
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

            sorted_s = sorted(summaries, key=lambda x: x.date, reverse=True)
            streak = 0
            for s in sorted_s:
                if s.productivity_score >= 60:
                    streak += 1
                else:
                    break

            half = max(len(summaries) // 2, 1)
            recent_avg = sum(s.productivity_score for s in summaries[:half]) / half
            older_avg = sum(s.productivity_score for s in summaries[half:]) / max(len(summaries[half:]), 1)
            trend = "up" if recent_avg > older_avg + 5 else "down" if recent_avg < older_avg - 5 else "same"
            days_data = len(summaries)

        else:
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


# ─── Department Comparison (Optimized) ────────────────────────────────────────

async def get_dept_comparison(target_date: date, db: AsyncSession) -> List[DepartmentComparisonRow]:
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    
    # Check if we should use today's live events or historical DailySummary
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    is_today = day_start >= today_start

    # Bulk fetch departments
    dept_result = await db.execute(select(Department))
    departments = dept_result.scalars().all()
    
    out = []
    
    for dept in departments:
        # Get employees for this dept
        emp_result = await db.execute(
            select(Employee).where(
                Employee.department_id == dept.id,
                Employee.is_active,
            )
        )
        employees = emp_result.scalars().all()
        if not employees:
            out.append(DepartmentComparisonRow(
                department_id=dept.id,
                department_name=dept.name,
                employee_count=0,
                online_count=0,
                avg_productivity_score=0.0,
                avg_active_seconds=0.0,
                avg_focus_sessions=0.0,
                avg_app_switches=0.0,
            ))
            continue
            
        emp_ids = [e.id for e in employees]

        if is_today:
             # Fast aggregation using DailySummary if available or fallback to slow loop for today only
             
             scores, actives, online_count = [], [], 0
             for emp in employees:
                 day_end = day_start + timedelta(days=1)
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
                     
             out.append(DepartmentComparisonRow(
                 department_id=dept.id,
                 department_name=dept.name,
                 employee_count=len(employees),
                 online_count=online_count,
                 avg_productivity_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
                 avg_active_seconds=float(sum(actives) / len(actives)) if actives else 0.0,
                 avg_focus_sessions=0.0,
                 avg_app_switches=0.0,
             ))
        else:
             # Look at historical daily summaries for performance!
             summ_result = await db.execute(
                 select(
                     func.avg(DailySummary.productivity_score).label("avg_pct"),
                     func.avg(DailySummary.active_seconds).label("avg_act"),
                     func.avg(DailySummary.focus_sessions).label("avg_fcs"),
                     func.avg(DailySummary.app_switches).label("avg_sw_"),
                 ).where(
                     DailySummary.employee_id.in_(emp_ids),
                     DailySummary.date == day_start,
                 )
             )
             agg = summ_result.one()
             
             out.append(DepartmentComparisonRow(
                 department_id=dept.id,
                 department_name=dept.name,
                 employee_count=len(employees),
                 online_count=0, # Not relevant for historical
                 avg_productivity_score=round(agg.avg_pct, 1) if agg.avg_pct else 0.0,
                 avg_active_seconds=float(agg.avg_act) if agg.avg_act else 0.0,
                 avg_focus_sessions=float(agg.avg_fcs) if agg.avg_fcs else 0.0,
                 avg_app_switches=float(agg.avg_sw_) if agg.avg_sw_ else 0.0,
             ))

    out.sort(key=lambda x: x.avg_productivity_score, reverse=True)
    return out


# ─── Anomalies (Paginated) ────────────────────────────────────────────────────

async def get_anomalies(
    page: int,
    page_size: int,
    db: AsyncSession,
    *,
    is_reviewed: Optional[bool] = None,
    employee_id: Optional[uuid.UUID] = None,
) -> PaginatedResult[AnomalyOut]:
    q = select(AnomalyLog, Employee.full_name.label("emp_name")).outerjoin(
        Employee, AnomalyLog.employee_id == Employee.id
    )
    if is_reviewed is not None:
        q = q.where(AnomalyLog.is_reviewed == is_reviewed)
    if employee_id:
        q = q.where(AnomalyLog.employee_id == employee_id)
    q = q.order_by(AnomalyLog.detected_at.desc())

    paginated = await paginate_query(db, q, page=page, page_size=page_size)
    
    # Map tuples to Out models
    out_items = []
    for a, name in paginated.items:
         out_items.append(AnomalyOut(
            id=a.id,
            employee_id=a.employee_id,
            employee_name=name,
            device_id=a.device_id,
            anomaly_type=a.anomaly_type.value if hasattr(a.anomaly_type, "value") else str(a.anomaly_type),
            detected_at=a.detected_at,
            description=a.description,
            metadata=a.event_metadata,
            is_reviewed=a.is_reviewed,
            reviewed_at=a.reviewed_at,
         ))
         
    return PaginatedResult(
        items=out_items,
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size
    )

async def review_anomaly(anomaly_id: uuid.UUID, admin_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(AnomalyLog).where(AnomalyLog.id == anomaly_id))
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        raise NotFoundError("Anomaly not found")
        
    anomaly.is_reviewed = True
    anomaly.reviewed_by = admin_id
    anomaly.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
