"""
PulseDesk Anomaly Detection Engine v4
Rule-based. Runs on every event batch from the agent.

ANOMALY TYPES & WHAT THEY MEAN:
1. excessive_idle       - No input for 45+ min during work hours
2. rapid_app_switching  - Admin-configurable switches per window
3. after_hours_activity - Active outside employee's work hours for 5+ min
4. unusual_app_usage    - Entertainment/gaming/social OR blocked domain accessed

BUG FIXES in v4:
- Fixed blocked domain matching: domain keyword extracted ("netflix.com" → "netflix")
  so it matches both browser URL titles AND native apps (e.g. "Netflix" app)
- Removed cooldown collision: blocked-domain violations use a separate cooldown key
  from distraction-category violations so one can't suppress the other
- Lowered distraction threshold from 20 min to 5 min per batch (it's a per-batch check)
- Blocked domain: ANY single match now triggers — no minimum time threshold
- All errors now logged at WARNING level instead of silently swallowed via debug
- Each anomaly check is isolated in its own try/except for resilience
"""

from datetime import datetime, timezone, timedelta
from typing import Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, String

from app.models import Device, AnomalyLog, AnomalyType, Employee
from app.core.logging import get_logger

log = get_logger("anomaly")

# Default Thresholds (Fallback if SystemSettings not found)
IDLE_THRESHOLD_MIN = 45
APP_SWITCH_RATE_HIGH = 4        # per configured window
APP_SWITCH_RATE_CRITICAL = 8
DISTRACTION_THRESHOLD_MIN = 5   # lowered: 5 min per batch is already a problem
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
        "use_case": "Switching between many apps in a short window — pattern of distraction.",
        "risk": "Low focus reduces output quality and indicates multitasking overload.",
        "recommended_action": "Review task assignments. Schedule dedicated focus blocks.",
        "severity": "low",
    },
    AnomalyType.after_hours_activity: {
        "title": "After-hours activity",
        "use_case": "Significant activity detected outside the employee's configured work hours.",
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


def _metadata_text(field_name: str):
    """
    Cross-version JSON text accessor for SQLAlchemy.
    SQLAlchemy 2.x prefers ``as_string()``, while older versions expose ``astext``.
    """
    expr = AnomalyLog.event_metadata[field_name]
    if hasattr(expr, "as_string"):
        return expr.as_string()
    if hasattr(expr, "astext"):
        return expr.astext
    return expr.cast(String)


def _extract_domain_keyword(domain: str) -> str:
    """
    Extract the brand keyword from a domain for flexible matching.
    "netflix.com" → "netflix"
    "twitch.tv"   → "twitch"
    "x.com"       → "x"    (short, so we also keep full domain for title matching)
    """
    return domain.split(".")[0].lower()


def _matches_blocked(domain: str, app: str, title: str) -> bool:
    """
    Check if an event's app name or window title matches a blocked domain.

    Matching strategy (any one hit = violation):
    1. Full domain in title       ("netflix.com" in "Netflix - Watch TV Shows...")
    2. Brand keyword in app name  ("netflix" in "netflix", "Netflix", "Netflix.exe")
    3. Brand keyword in title     ("netflix" in window title)

    This catches both:
    - Browser-based access (title will contain the URL or site name)
    - Native desktop apps (app name will contain the brand)
    """
    domain_lower = domain.lower()
    app_lower = app.lower()
    title_lower = title.lower()
    keyword = _extract_domain_keyword(domain_lower)

    if domain_lower in title_lower:
        return True
    if keyword and keyword in app_lower:
        return True
    if keyword and keyword in title_lower:
        return True
    return False


async def check_anomalies(device: Device, events: list, db: AsyncSession) -> None:
    if not events:
        return
    now = datetime.now(timezone.utc)
    employee_id = device.employee_id

    # Each check is isolated — one failure does NOT stop the others
    for check_fn, name in [
        (_check_excessive_idle, "excessive_idle"),
        (_check_rapid_switching, "rapid_switching"),
        (_check_after_hours, "after_hours"),
        (_check_distraction, "distraction"),
        (_check_blocked_domains, "blocked_domains"),
    ]:
        try:
            await check_fn(device, events, employee_id, now, db)
        except Exception as e:
            log.warning(f"anomaly_check_failed check={name} error={e}")


async def _can_create(employee_id, device_id, anomaly_type, cooldown_hours, db, *, extra_filter=None):
    """
    Returns True if no anomaly of this type was created for this employee+device
    within the cooldown window. Uses device_id so per-device cooldowns work correctly.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    query = select(func.count(AnomalyLog.id)).where(
        AnomalyLog.employee_id == employee_id,
        AnomalyLog.device_id == device_id,
        AnomalyLog.anomaly_type == anomaly_type,
        AnomalyLog.detected_at >= since,
    )
    if extra_filter is not None:
        query = query.where(extra_filter)
    result = await db.execute(query)
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
    except Exception as e:
        log.warning(f"anomaly_flush_failed: {e}")
        return

    # Broadcast to dashboard WebSocket
    try:
        from app.services.ws_broadcaster import broadcast_anomaly
        import asyncio
        asyncio.create_task(broadcast_anomaly({
            "employee_id": str(employee_id),
            "type": str(anomaly_type),
            "title": meta.get("title", str(anomaly_type)),
            "description": description,
            "severity": full_meta["severity"],
            "recommended_action": meta.get("recommended_action", ""),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception as e:
        log.warning(f"ws_anomaly_broadcast_failed: {e}")

    log.warning("anomaly_detected",
                type=str(anomaly_type),
                severity=full_meta["severity"],
                employee=str(employee_id),
                desc=description[:100])


# ─── Individual Checks ────────────────────────────────────────────────────────

async def _check_excessive_idle(device, events, employee_id, now, db):
    # Load admin-configured threshold
    from app.models import SystemSettings, ActivityEvent
    settings_result = await db.execute(select(SystemSettings))
    sys_settings = settings_result.scalar_one_or_none()
    idle_threshold = sys_settings.excessive_idle_threshold_minutes if sys_settings else IDLE_THRESHOLD_MIN

    # Only flag during work hours 8AM-8PM
    hour = now.hour
    if not (8 <= hour <= 20):
        return

    # Check continuous sum over the past `idle_threshold` minutes
    since = now - timedelta(minutes=idle_threshold)
    result = await db.execute(
        select(func.sum(ActivityEvent.sample_duration_seconds))
        .where(
            ActivityEvent.device_id == device.id,
            ActivityEvent.timestamp >= since,
            ActivityEvent.activity_type.in_(("idle", "away", "locked"))
        )
    )
    total_idle = result.scalar() or 0

    if total_idle < idle_threshold * 60 * 0.8:  # Allow 20% margin for missing agent cycles
        return

    if not await _can_create(employee_id, device.id, AnomalyType.excessive_idle, 1, db):
        return

    await _create(
        employee_id, device.id,
        AnomalyType.excessive_idle,
        f"Idle for ~{int(total_idle // 60)} minutes during work hours. Threshold: {idle_threshold} min.",
        {"idle_seconds": int(total_idle), "hour": hour},
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
        duration_seconds = max((batch_end - batch_start).total_seconds(), 5)
    except Exception:
        return

    # Load admin-configured thresholds from SystemSettings
    from app.models import SystemSettings
    settings_result = await db.execute(select(SystemSettings))
    sys_settings = settings_result.scalar_one_or_none()

    if sys_settings:
        high_threshold = sys_settings.rapid_switching_high_threshold
        critical_threshold = sys_settings.rapid_switching_critical_threshold
        window_sec = sys_settings.rapid_switching_window_seconds
    else:
        high_threshold = APP_SWITCH_RATE_HIGH
        critical_threshold = APP_SWITCH_RATE_CRITICAL
        window_sec = 60

    # Rate = switches per configured window (e.g. per 60s)
    rate_per_window = switches / (duration_seconds / window_sec)

    if rate_per_window < high_threshold:
        return

    if not await _can_create(employee_id, device.id, AnomalyType.rapid_app_switching, 1, db):
        return

    severity = "high" if rate_per_window >= critical_threshold else "low"
    await _create(
        employee_id, device.id,
        AnomalyType.rapid_app_switching,
        f"App switching rate: {rate_per_window:.1f} per {window_sec}s over {duration_seconds:.0f}s ({switches} switches).",
        {"rate_per_window": round(rate_per_window, 2), "switches": switches,
         "window_seconds": window_sec, "severity_override": severity},
        db,
    )


async def _check_after_hours(device, events, employee_id, now, db):
    # Load admin-configured threshold
    from app.models import SystemSettings, ActivityEvent
    settings_result = await db.execute(select(SystemSettings))
    sys_settings = settings_result.scalar_one_or_none()
    after_hours_threshold = sys_settings.after_hours_min_active_minutes if sys_settings else AFTER_HOURS_MIN_ACTIVE_MIN

    emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = emp_result.scalar_one_or_none()
    if not emp:
        return

    start_hr = getattr(emp, 'work_start_hour', 9)
    end_hr = getattr(emp, 'work_end_hour', 18)
    tz_str = getattr(emp, 'timezone', 'UTC')

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc

    # Check if we are currently outside work hours to avoid running this on every event unnecessarily
    local_now = now.astimezone(tz)
    if start_hr <= local_now.hour < end_hr:
        return

    # Sum total active time today outside work hours
    since = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    
    # We query the DB for all events today for this employee
    # that are active, and evaluate if they were outside hours.
    result = await db.execute(
        select(ActivityEvent.timestamp, ActivityEvent.sample_duration_seconds)
        .where(
            ActivityEvent.employee_id == employee_id,
            ActivityEvent.activity_type == "active",
            ActivityEvent.timestamp >= since
        )
    )
    
    active_secs = 0
    for row in result.all():
        try:
            local_time = row.timestamp.astimezone(tz)
            h = local_time.hour
            if h >= end_hr or h < start_hr:
                active_secs += row.sample_duration_seconds
        except Exception:
            continue

    if active_secs < after_hours_threshold * 60:
        return

    # Cooldown: once per day
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
        f"Active for {int(active_secs // 60)} min outside work hours "
        f"(configured: {start_hr}:00–{end_hr}:00).",
        {"active_seconds": int(active_secs), "work_start": start_hr, "work_end": end_hr},
        db,
    )


async def _check_distraction(device, events, employee_id, now, db):
    """
    Flags entertainment/gaming/social usage using a rolling window of 1 hour.
    """
    from app.services.categorizer import is_distraction_category, categorize_app
    from app.models import SystemSettings, ActivityEvent

    # Load admin-configured threshold
    settings_result = await db.execute(select(SystemSettings))
    sys_settings = settings_result.scalar_one_or_none()
    distraction_threshold = sys_settings.distraction_threshold_minutes if sys_settings else DISTRACTION_THRESHOLD_MIN

    # We evaluate distractions over the past 1 hour rolling window
    since = now - timedelta(hours=1)
    
    # Query all active apps in the past 1 hour for this device to summarize total distraction time
    result = await db.execute(
        select(ActivityEvent.active_app, func.sum(ActivityEvent.sample_duration_seconds))
        .where(
            ActivityEvent.device_id == device.id,
            ActivityEvent.timestamp >= since,
            ActivityEvent.active_app.isnot(None),
            ActivityEvent.activity_type == "active"
        )
        .group_by(ActivityEvent.active_app)
    )
    
    distraction_secs = 0
    distraction_apps: Set[str] = set()
    
    for row in result.all():
        app = row[0]
        duration = row[1] or 0
        if app:
            cat = categorize_app(app)
            if is_distraction_category(cat):
                distraction_secs += duration
                distraction_apps.add(app)

    if distraction_secs < distraction_threshold * 60:
        return

    # 2hr cooldown specifically for category-based distraction (not domain-based)
    cooldown_since = now - timedelta(hours=2)
    result = await db.execute(
        select(func.count(AnomalyLog.id)).where(
            AnomalyLog.employee_id == employee_id,
            AnomalyLog.device_id == device.id,
            AnomalyLog.anomaly_type == AnomalyType.unusual_app_usage,
            AnomalyLog.detected_at >= cooldown_since,
            # Only count non-domain violations in this cooldown
            _metadata_text("violation_type") != "blocked_domain",
        )
    )
    if (result.scalar() or 0) > 0:
        return

    severity = "high" if distraction_secs >= 30 * 60 else "medium"
    apps_list = list(distraction_apps)[:5]
    await _create(
        employee_id, device.id,
        AnomalyType.unusual_app_usage,
        f"Distraction apps used for {int(distraction_secs // 60)} min: {', '.join(apps_list)}.",
        {"apps": apps_list, "distraction_seconds": int(distraction_secs),
         "violation_type": "distraction_category", "severity_override": severity},
        db,
    )


async def _check_blocked_domains(device, events, employee_id, now, db):
    """
    Checks every event's active_app AND active_window_title against the blocklist.

    FIXED: Extracts brand keyword from domain ("netflix.com" → "netflix") so it
    matches both:
    - Browser tabs: title = "Netflix - Browse Movies... - Chrome"
    - Native apps:  app  = "Netflix", "netflix.exe", "Netflix.exe"

    ANY single match triggers an alert — no minimum time threshold.
    Has its own 1-hour cooldown independent from the distraction-category check.
    """
    from app.services import blocklist_store

    active_rules = await blocklist_store.get_active_rules(db)
    if not active_rules:
        return

    violations: list[dict] = []
    for e in events:
        raw_title = getattr(e, 'active_window_title', None) or ""
        raw_app = getattr(e, 'active_app', None) or ""
        if not raw_title and not raw_app:
            continue

        for rule in active_rules:
            domain = rule.get("domain", "")
            if not domain:
                continue
            if _matches_blocked(domain, raw_app, raw_title):
                violations.append({
                    "domain": domain,
                    "app": raw_app,
                    "title": raw_title[:120],
                    "severity": rule.get("severity", "medium"),
                    "category": rule.get("category", "general"),
                })
                break  # one rule match per event is enough

    if not violations:
        return

    # Separate 1-hour cooldown for blocked-domain violations
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(
        select(func.count(AnomalyLog.id)).where(
            AnomalyLog.employee_id == employee_id,
            AnomalyLog.device_id == device.id,
            AnomalyLog.anomaly_type == AnomalyType.unusual_app_usage,
            AnomalyLog.detected_at >= since,
            _metadata_text("violation_type") == "blocked_domain",
        )
    )
    if (result.scalar() or 0) > 0:
        return

    # Group violations by domain for a clean summary
    domains_hit: dict[str, dict] = {}
    for v in violations:
        d = v["domain"]
        if d not in domains_hit:
            domains_hit[d] = {"count": 0, "severity": v["severity"],
                              "category": v["category"], "apps": set()}
        domains_hit[d]["count"] += 1
        if v["app"]:
            domains_hit[d]["apps"].add(v["app"])

    domain_list = list(domains_hit.keys())
    # Use the highest severity across all matched domains
    severity_order = {"low": 0, "medium": 1, "high": 2}
    top_severity = max(
        (d["severity"] for d in domains_hit.values()),
        key=lambda s: severity_order.get(s, 1),
        default="medium"
    )
    total_hits = sum(d["count"] for d in domains_hit.values())
    apps_seen = list({a for d in domains_hit.values() for a in d["apps"]})[:3]

    desc = (
        f"Blocked site accessed: {', '.join(domain_list)} "
        f"({total_hits} event(s))"
        + (f" via {', '.join(apps_seen)}" if apps_seen else "")
        + "."
    )

    await _create(
        employee_id, device.id,
        AnomalyType.unusual_app_usage,
        desc,
        {
            "blocked_domains": domain_list,
            "domain_details": {
                d: {"count": v["count"], "severity": v["severity"],
                    "category": v["category"], "apps": list(v["apps"])}
                for d, v in domains_hit.items()
            },
            "violation_count": total_hits,
            "violation_type": "blocked_domain",
            "severity_override": top_severity,
        },
        db,
    )
