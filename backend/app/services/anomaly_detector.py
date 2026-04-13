"""
PulseDesk Anomaly Detection Engine v3
Rule-based only. Runs on every event batch.

ANOMALY TYPES & WHAT THEY MEAN:
1. excessive_idle     - No input for 45+ min during work hours (8AM-8PM)
2. rapid_app_switching - 4+ app switches per minute = distracted
3. after_hours_activity - Active between 10PM-6AM for 5+ min
4. unusual_app_usage  - Entertainment/gaming/social OR blocked domain accessed
"""

from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Device, AnomalyLog, AnomalyType
from app.core.logging import get_logger

log = get_logger("anomaly")

# Thresholds
IDLE_THRESHOLD_MIN = 45
APP_SWITCH_RATE_HIGH = 4      # per minute
APP_SWITCH_RATE_CRITICAL = 8
DISTRACTION_THRESHOLD_MIN = 20
AFTER_HOURS_START = 22
AFTER_HOURS_END = 6
AFTER_HOURS_MIN_ACTIVE_MIN = 5

ANOMALY_META = {
    AnomalyType.excessive_idle: {
        "title": "Excessive idle time",
        "use_case": "No keyboard/mouse input for 45+ minutes during work hours.",
        "risk": "Unattended device is a security risk on shared/sensitive systems.",
        "recommended_action": "Check in with employee. If recurring, review break schedule.",
        "severity": "medium",
    },
    AnomalyType.rapid_app_switching: {
        "title": "Rapid app switching",
        "use_case": "Switching between 4+ apps per minute — pattern of distraction.",
        "risk": "Low focus reduces output quality and indicates multitasking overload.",
        "recommended_action": "Review task assignments. Schedule dedicated focus blocks.",
        "severity": "low",
    },
    AnomalyType.after_hours_activity: {
        "title": "After-hours activity",
        "use_case": "Significant activity detected between 10PM and 6AM.",
        "risk": "Burnout risk if recurring. Could indicate unauthorized access.",
        "recommended_action": "Verify if approved overtime. Check physical access logs.",
        "severity": "medium",
    },
    AnomalyType.unusual_app_usage: {
        "title": "Policy violation / distraction app",
        "use_case": "Time on entertainment, gaming, social media, or a blocked domain.",
        "risk": "Lost productivity. Blocked sites may be data exfiltration vectors.",
        "recommended_action": "First offense: conversation. Repeated: HR process.",
        "severity": "medium",
    },
}


async def check_anomalies(device: Device, events: list, db: AsyncSession) -> None:
    if not events:
        return
    now = datetime.now(timezone.utc)
    employee_id = device.employee_id

    await _check_excessive_idle(device, events, employee_id, now, db)
    await _check_rapid_switching(device, events, employee_id, now, db)
    await _check_after_hours(device, events, employee_id, now, db)
    await _check_distraction(device, events, employee_id, now, db)
    await _check_blocked_domains(device, events, employee_id, now, db)


async def _can_create(employee_id, device_id, anomaly_type, cooldown_hours, db):
    since = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    result = await db.execute(
        select(func.count(AnomalyLog.id)).where(
            AnomalyLog.employee_id == employee_id,
            AnomalyLog.device_id == device_id,
            AnomalyLog.anomaly_type == anomaly_type,
            AnomalyLog.detected_at >= since,
        )
    )
    return (result.scalar() or 0) == 0


async def _create(employee_id, device_id, anomaly_type, description, metadata, db):
    meta = ANOMALY_META.get(anomaly_type, {})
    full_meta = {
        **metadata,
        "use_case": meta.get("use_case", ""),
        "risk": meta.get("risk", ""),
        "recommended_action": meta.get("recommended_action", ""),
        "severity": metadata.get("severity_override", meta.get("severity", "medium")),
    }
    anomaly = AnomalyLog(
        employee_id=employee_id,
        device_id=device_id,
        anomaly_type=anomaly_type,
        description=description,
        event_metadata=full_meta,
    )
    db.add(anomaly)
    try:
        await db.flush()
    except Exception:
        pass

    # Broadcast to dashboard
    try:
        from app.services.ws_broadcaster import broadcast_anomaly
        await broadcast_anomaly({
            "employee_id": str(employee_id),
            "type": str(anomaly_type),
            "title": meta.get("title", str(anomaly_type)),
            "description": description,
            "severity": full_meta["severity"],
            "recommended_action": meta.get("recommended_action", ""),
        })
    except Exception as e:
        log.debug(f"ws_anomaly_broadcast_failed: {e}")

    log.warning("anomaly_detected",
                type=str(anomaly_type),
                severity=full_meta["severity"],
                employee=str(employee_id),
                desc=description[:80])


async def _check_excessive_idle(device, events, employee_id, now, db):
    # Only flag during work hours 8AM-8PM
    hour = now.hour
    if not (8 <= hour <= 20):
        return

    total_idle = sum(
        e.idle_duration_seconds for e in events
        if hasattr(e, 'activity_type') and e.activity_type == "idle"
    )
    if total_idle < IDLE_THRESHOLD_MIN * 60:
        return

    if not await _can_create(employee_id, device.id, AnomalyType.excessive_idle, 1, db):
        return

    await _create(
        employee_id, device.id,
        AnomalyType.excessive_idle,
        f"Idle for {total_idle // 60} minutes during work hours. Threshold: {IDLE_THRESHOLD_MIN} min.",
        {"idle_seconds": total_idle, "hour": hour},
        db,
    )


async def _check_rapid_switching(device, events, employee_id, now, db):
    if len(events) < 3:
        return

    switches = 0
    prev_app = None
    for e in events:
        app = getattr(e, 'active_app', None)
        if app and app != prev_app:
            if prev_app is not None:
                switches += 1
            prev_app = app

    if switches == 0:
        return

    try:
        batch_start = events[0].timestamp
        batch_end = events[-1].timestamp
        duration_min = max((batch_end - batch_start).total_seconds() / 60, 1)
    except Exception:
        return

    rate = switches / duration_min
    if rate < APP_SWITCH_RATE_HIGH:
        return

    if not await _can_create(employee_id, device.id, AnomalyType.rapid_app_switching, 1, db):
        return

    severity = "high" if rate >= APP_SWITCH_RATE_CRITICAL else "low"
    await _create(
        employee_id, device.id,
        AnomalyType.rapid_app_switching,
        f"App switching rate: {rate:.1f}/min over {duration_min:.0f} min. ({switches} switches)",
        {"rate": round(rate, 2), "switches": switches, "severity_override": severity},
        db,
    )


async def _check_after_hours(device, events, employee_id, now, db):
    after_hours_events = []
    for e in events:
        try:
            h = e.timestamp.hour
            if h >= AFTER_HOURS_START or h < AFTER_HOURS_END:
                if getattr(e, 'activity_type', None) == "active":
                    after_hours_events.append(e)
        except Exception:
            continue

    active_secs = sum(getattr(e, 'sample_duration_seconds', 30) for e in after_hours_events)
    if active_secs < AFTER_HOURS_MIN_ACTIVE_MIN * 60:
        return

    # Cooldown: once per day
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(AnomalyLog.id)).where(
            AnomalyLog.employee_id == employee_id,
            AnomalyLog.anomaly_type == AnomalyType.after_hours_activity,
            AnomalyLog.detected_at >= since,
        )
    )
    if (result.scalar() or 0) > 0:
        return

    await _create(
        employee_id, device.id,
        AnomalyType.after_hours_activity,
        f"Active for {active_secs // 60} min outside work hours (10PM–6AM).",
        {"active_seconds": active_secs},
        db,
    )


async def _check_distraction(device, events, employee_id, now, db):
    from app.services.categorizer import is_distraction_category, categorize_app

    distraction_secs = 0
    distraction_apps = set()
    for e in events:
        app = getattr(e, 'active_app', None)
        if app:
            cat = categorize_app(app)
            if is_distraction_category(cat):
                distraction_secs += getattr(e, 'sample_duration_seconds', 30)
                distraction_apps.add(app)

    if distraction_secs < DISTRACTION_THRESHOLD_MIN * 60:
        return

    if not await _can_create(employee_id, device.id, AnomalyType.unusual_app_usage, 2, db):
        return

    severity = "high" if distraction_secs >= 60 * 60 else "medium"
    apps_list = list(distraction_apps)[:3]
    await _create(
        employee_id, device.id,
        AnomalyType.unusual_app_usage,
        f"Distraction apps used for {distraction_secs // 60} min: {', '.join(apps_list)}.",
        {"apps": apps_list, "distraction_seconds": distraction_secs, "severity_override": severity},
        db,
    )


async def _check_blocked_domains(device, events, employee_id, now, db):
    try:
        from app.api.v1.routes.blocker import _blocked_domains
        if not _blocked_domains:
            return

        blocked = [v["domain"] for v in _blocked_domains.values() if v.get("is_active")]
        if not blocked:
            return

        violations = []
        for e in events:
            title = (getattr(e, 'active_window_title', None) or "").lower()
            app = (getattr(e, 'active_app', None) or "").lower()
            for domain in blocked:
                if domain.lower() in title or domain.lower() in app:
                    violations.append(domain)
                    break

        if not violations:
            return

        if not await _can_create(employee_id, device.id, AnomalyType.unusual_app_usage, 1, db):
            return

        domains_hit = list(set(violations))
        await _create(
            employee_id, device.id,
            AnomalyType.unusual_app_usage,
            f"Blocked domain accessed: {', '.join(domains_hit)} ({len(violations)} times).",
            {
                "blocked_domains": domains_hit,
                "violation_count": len(violations),
                "violation_type": "blocked_domain",
                "severity_override": "high",
            },
            db,
        )
    except Exception as e:
        log.debug(f"blocked_domain_check_error: {e}")
