"""
Daily summary aggregator - computes DailySummary for each employee.
Can be run at any time - safe to re-run (upserts).
Also exposed as an API endpoint so admin can force recompute.
"""

from datetime import datetime, timezone, timedelta, date
from typing import Optional
from collections import defaultdict

from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.models import (
    Employee, ActivityEvent, DailySummary, AnomalyLog,
)
from app.services.categorizer import is_productive_category
from app.core.logging import get_logger

log = get_logger("aggregator")


async def compute_daily_summaries(target_date: Optional[date] = None):
    """Compute DailySummary for all employees. Defaults to today."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    async with AsyncSessionLocal() as db:
        emp_result = await db.execute(select(Employee).where(Employee.is_active))
        employees = emp_result.scalars().all()
        computed = 0

        for employee in employees:
            try:
                await _compute_for_employee(employee, day_start, day_end, db)
                computed += 1
            except Exception as e:
                log.error("summary_failed", employee_id=str(employee.id), error=str(e))

        await db.commit()
        log.info("summaries_computed", date=str(target_date), count=computed)
        return computed


async def _compute_for_employee(employee, day_start, day_end, db):
    result = await db.execute(
        select(ActivityEvent)
        .where(
            ActivityEvent.employee_id == employee.id,
            ActivityEvent.timestamp >= day_start,
            ActivityEvent.timestamp < day_end,
        )
        .order_by(ActivityEvent.timestamp)
    )
    events = result.scalars().all()

    if not events:
        return

    # ── Time breakdown ────────────────────────────────────────────────────────
    total_tracked = sum(e.sample_duration_seconds for e in events)
    active_secs = sum(e.sample_duration_seconds for e in events if e.activity_type == "active")
    idle_secs = sum(e.sample_duration_seconds for e in events if e.activity_type == "idle")

    # ── Hourly heatmap ────────────────────────────────────────────────────────
    hourly: dict = defaultdict(int)
    for e in events:
        if e.activity_type == "active":
            hourly[str(e.timestamp.hour)] += e.sample_duration_seconds
    hourly_dict = {str(h): hourly.get(str(h), 0) for h in range(24)}

    # ── App usage ─────────────────────────────────────────────────────────────
    app_time: dict = defaultdict(int)
    app_cat: dict = {}
    for e in events:
        if e.active_app:
            app_time[e.active_app] += e.sample_duration_seconds
            if e.app_category:
                app_cat[e.active_app] = e.app_category

    top_app = max(app_time, key=app_time.get) if app_time else None
    cat_time: dict = defaultdict(int)
    for app, secs in app_time.items():
        cat_time[app_cat.get(app, "other")] += secs
    top_category = max(cat_time, key=cat_time.get) if cat_time else None

    # ── Focus sessions (25+ min in same app) ─────────────────────────────────
    focus_secs = 0
    focus_count = 0
    app_switches = 0
    current_app = None
    current_duration = 0

    for e in events:
        if e.active_app != current_app:
            if current_app and current_duration >= 1500:
                focus_count += 1
                focus_secs += current_duration
            if current_app is not None:
                app_switches += 1
            current_app = e.active_app
            current_duration = e.sample_duration_seconds
        else:
            current_duration += e.sample_duration_seconds

    if current_app and current_duration >= 1500:
        focus_count += 1
        focus_secs += current_duration

    # ── Productivity score ────────────────────────────────────────────────────
    productive_secs = sum(
        e.sample_duration_seconds for e in events
        if is_productive_category(e.app_category)
    )
    active_ratio = active_secs / max(total_tracked, 1)
    productive_ratio = productive_secs / max(active_secs, 1) if active_secs > 0 else 0
    switches_per_hour = (app_switches / max(total_tracked / 3600, 0.1))
    switch_penalty = min(0.25, switches_per_hour / 60)
    focus_bonus = min(0.15, focus_count * 0.03)
    score = (active_ratio * 0.5 + productive_ratio * 0.4 - switch_penalty + focus_bonus) * 100
    productivity_score = round(max(0.0, min(100.0, score)), 1)

    # ── Anomaly count ─────────────────────────────────────────────────────────
    anomaly_result = await db.execute(
        select(func.count(AnomalyLog.id)).where(
            AnomalyLog.employee_id == employee.id,
            AnomalyLog.detected_at >= day_start,
            AnomalyLog.detected_at < day_end,
        )
    )
    anomaly_count = anomaly_result.scalar() or 0

    # ── Upsert DailySummary ───────────────────────────────────────────────────
    existing = await db.execute(
        select(DailySummary).where(
            DailySummary.employee_id == employee.id,
            DailySummary.date == day_start,
        )
    )
    summary = existing.scalar_one_or_none()

    vals = dict(
        total_tracked_seconds=total_tracked,
        active_seconds=active_secs,
        idle_seconds=idle_secs,
        focus_seconds=focus_secs,
        productivity_score=productivity_score,
        focus_sessions=focus_count,
        app_switches=app_switches,
        top_app=top_app,
        top_category=top_category,
        hourly_active_seconds=hourly_dict,
        anomaly_count=anomaly_count,
        computed_at=datetime.now(timezone.utc),
    )

    if summary:
        for k, v in vals.items():
            setattr(summary, k, v)
    else:
        db.add(DailySummary(employee_id=employee.id, date=day_start, **vals))

    log.debug("summary_done", employee=str(employee.id), score=productivity_score,
              active_min=active_secs // 60)
