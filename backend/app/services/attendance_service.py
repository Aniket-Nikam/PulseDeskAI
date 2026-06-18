"""
Attendance Service — Business logic for the attendance system.
Handles check-in/out, geofence validation, lunch breaks, status computation.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Date

from app.models import (
    AttendanceSettings, AttendanceLocation, AttendanceRecord,
    LunchBreakLog, AttendanceMode, AttendanceStatus, Employee,
)
from app.services.geofence import find_nearest_location
from app.core.logging import get_logger

log = get_logger("attendance")


# ── Settings ──────────────────────────────────────────────────────────────────

async def get_attendance_settings(db: AsyncSession) -> Optional[AttendanceSettings]:
    """Get the singleton attendance settings row, or None if not configured."""
    result = await db.execute(select(AttendanceSettings))
    return result.scalar_one_or_none()


async def setup_attendance(
    db: AsyncSession,
    mode: str,
    admin_id: uuid.UUID,
) -> AttendanceSettings:
    """Initial setup — create or update the singleton settings row."""
    result = await db.execute(select(AttendanceSettings))
    settings = result.scalar_one_or_none()

    if settings:
        settings.mode = AttendanceMode(mode)
        settings.is_configured = True
        settings.updated_by = admin_id
    else:
        settings = AttendanceSettings(
            mode=AttendanceMode(mode),
            is_configured=True,
            updated_by=admin_id,
        )
        db.add(settings)

    await db.commit()
    await db.refresh(settings)
    log.info("attendance_setup", mode=mode, admin_id=str(admin_id))
    return settings


async def update_attendance_settings(
    db: AsyncSession,
    data: dict,
    admin_id: uuid.UUID,
) -> AttendanceSettings:
    """Update attendance settings."""
    result = await db.execute(select(AttendanceSettings))
    settings = result.scalar_one_or_none()
    if not settings:
        raise ValueError("Attendance not configured. Run setup first.")

    for key, value in data.items():
        if hasattr(settings, key) and key not in ("id", "created_at"):
            if key == "mode":
                setattr(settings, key, AttendanceMode(value))
            else:
                setattr(settings, key, value)

    settings.updated_by = admin_id
    await db.commit()
    await db.refresh(settings)
    return settings


# ── Locations ─────────────────────────────────────────────────────────────────

async def list_locations(db: AsyncSession) -> List[AttendanceLocation]:
    result = await db.execute(
        select(AttendanceLocation).order_by(AttendanceLocation.created_at.desc())
    )
    return list(result.scalars().all())


async def create_location(
    db: AsyncSession,
    name: str,
    latitude: float,
    longitude: float,
    radius_meters: int,
    applies_to: str,
    department_id: Optional[uuid.UUID],
    admin_id: uuid.UUID,
) -> AttendanceLocation:
    loc = AttendanceLocation(
        name=name,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        applies_to=applies_to,
        department_id=department_id,
        created_by=admin_id,
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    log.info("attendance_location_created", name=name, location_id=str(loc.id))
    return loc


async def update_location(
    db: AsyncSession,
    location_id: uuid.UUID,
    data: dict,
) -> Optional[AttendanceLocation]:
    result = await db.execute(
        select(AttendanceLocation).where(AttendanceLocation.id == location_id)
    )
    loc = result.scalar_one_or_none()
    if not loc:
        return None

    for key, value in data.items():
        if hasattr(loc, key) and key not in ("id", "created_at", "created_by"):
            setattr(loc, key, value)

    await db.commit()
    await db.refresh(loc)
    return loc


async def delete_location(db: AsyncSession, location_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(AttendanceLocation).where(AttendanceLocation.id == location_id)
    )
    loc = result.scalar_one_or_none()
    if not loc:
        return False

    # Nullify FK references in AttendanceRecord to avoid IntegrityError
    from sqlalchemy import update
    await db.execute(
        update(AttendanceRecord)
        .where(AttendanceRecord.check_in_location_id == location_id)
        .values(check_in_location_id=None)
    )
    await db.execute(
        update(AttendanceRecord)
        .where(AttendanceRecord.check_out_location_id == location_id)
        .values(check_out_location_id=None)
    )

    await db.delete(loc)
    await db.commit()
    log.info("attendance_location_deleted", location_id=str(location_id), name=loc.name)
    return True


# ── Check-in / Check-out ─────────────────────────────────────────────────────

def _parse_work_time(time_str: str, ref_date: datetime) -> datetime:
    """Parse HH:MM string into a datetime on the given reference date."""
    h, m = int(time_str.split(":")[0]), int(time_str.split(":")[1])
    return ref_date.replace(hour=h, minute=m, second=0, microsecond=0)


async def check_in(
    db: AsyncSession,
    employee_id: uuid.UUID,
    latitude: Optional[float],
    longitude: Optional[float],
) -> dict:
    """Process employee check-in with geofence validation."""
    now = datetime.now(timezone.utc)
    today_date = now.date()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Check for existing record today (cast to Date for robust comparison)
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            cast(AttendanceRecord.date, Date) == today_date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing and existing.check_in_time:
        log.debug("check_in_already_exists", employee_id=str(employee_id))
        return {"error": "Already checked in today", "record_id": str(existing.id)}

    # Get settings
    settings = await get_attendance_settings(db)
    if not settings or not settings.is_configured:
        return {"error": "Attendance system not configured"}

    # Geofence validation
    within_geofence = False
    matched_location_id = None
    is_remote = False

    if latitude is not None and longitude is not None:
        locations = await list_locations(db)
        active_locs = [
            {
                "id": loc.id,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "radius_meters": loc.radius_meters,
            }
            for loc in locations
            if loc.is_active
        ]

        nearest = find_nearest_location(latitude, longitude, active_locs)
        if nearest:
            within_geofence = True
            matched_location_id = nearest["id"]
        elif not settings.allow_remote_checkin:
            return {
                "error": "You are not within any approved location. Move closer and try again.",
                "nearest_distance": None,
            }
        else:
            is_remote = True
    elif not settings.allow_remote_checkin:
        return {"error": "Location is required for check-in"}
    else:
        is_remote = True

    # Determine status
    work_start = _parse_work_time(settings.work_start_time, now)
    late_cutoff = work_start + timedelta(minutes=settings.late_threshold_minutes)
    status = AttendanceStatus.present if now <= late_cutoff else AttendanceStatus.late

    if existing:
        existing.check_in_time = now
        existing.check_in_latitude = latitude
        existing.check_in_longitude = longitude
        existing.check_in_location_id = matched_location_id
        existing.check_in_within_geofence = within_geofence
        existing.status = status
        existing.is_remote = is_remote
        record = existing
    else:
        record = AttendanceRecord(
            employee_id=employee_id,
            date=today,
            check_in_time=now,
            check_in_latitude=latitude,
            check_in_longitude=longitude,
            check_in_location_id=matched_location_id,
            check_in_within_geofence=within_geofence,
            status=status,
            is_remote=is_remote,
        )
        db.add(record)

    await db.commit()
    await db.refresh(record)

    log.info("attendance_check_in", employee_id=str(employee_id), status=status.value, within_geofence=within_geofence)
    return {
        "success": True,
        "record_id": str(record.id),
        "status": status.value,
        "check_in_time": record.check_in_time.isoformat(),
        "within_geofence": within_geofence,
        "is_remote": is_remote,
    }


async def check_out(
    db: AsyncSession,
    employee_id: uuid.UUID,
    latitude: Optional[float],
    longitude: Optional[float],
    bypass_location: bool = False,
) -> dict:
    """Process employee check-out with duration calculation."""
    now = datetime.now(timezone.utc)
    today_date = now.date()
    now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            cast(AttendanceRecord.date, Date) == today_date,
        )
    )
    record = result.scalar_one_or_none()
    if not record or not record.check_in_time:
        return {"error": "No check-in record found for today"}
    if record.check_out_time:
        return {"error": "Already checked out today"}

    settings = await get_attendance_settings(db)

    # Geofence validation for checkout
    within_geofence = False
    matched_location_id = None

    if latitude is not None and longitude is not None:
        locations = await list_locations(db)
        active_locs = [
            {
                "id": loc.id,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "radius_meters": loc.radius_meters,
            }
            for loc in locations
            if loc.is_active
        ]
        nearest = find_nearest_location(latitude, longitude, active_locs)
        if nearest:
            within_geofence = True
            matched_location_id = nearest["id"]
        elif not bypass_location and settings and settings.require_location_for_checkout:
            return {"error": "You must be within an approved location to check out"}
    elif not bypass_location and settings and settings.require_location_for_checkout:
        return {"error": "Location is required for check-out"}

    record.check_out_time = now
    record.check_out_latitude = latitude
    record.check_out_longitude = longitude
    record.check_out_location_id = matched_location_id
    record.check_out_within_geofence = within_geofence

    # Calculate work duration
    total_seconds = int((now - record.check_in_time).total_seconds())
    record.total_work_seconds = max(total_seconds, 0)

    # Deduct lunch if applicable
    lunch_deducted = 0
    if settings and settings.lunch_break_enabled and settings.auto_deduct_lunch:
        lunch_deducted = settings.lunch_break_duration_minutes * 60
    else:
        # Sum actual lunch break durations
        lunch_result = await db.execute(
            select(func.coalesce(func.sum(LunchBreakLog.duration_seconds), 0)).where(
                LunchBreakLog.attendance_record_id == record.id,
                LunchBreakLog.ended_at.isnot(None),
            )
        )
        lunch_deducted = lunch_result.scalar() or 0

    record.lunch_deducted_seconds = lunch_deducted
    record.effective_work_seconds = max(record.total_work_seconds - lunch_deducted, 0)

    # Update status based on total hours
    if settings:
        effective_hours = record.effective_work_seconds / 3600
        if effective_hours < settings.half_day_threshold_hours:
            record.status = AttendanceStatus.half_day

        # Overtime
        if settings.overtime_enabled:
            overtime_threshold = settings.overtime_after_hours * 3600
            if record.effective_work_seconds > overtime_threshold:
                record.overtime_seconds = int(record.effective_work_seconds - overtime_threshold)

    await db.commit()
    await db.refresh(record)

    log.info("attendance_check_out", employee_id=str(employee_id), total_seconds=total_seconds)
    return {
        "success": True,
        "record_id": str(record.id),
        "check_out_time": record.check_out_time.isoformat(),
        "total_work_seconds": record.total_work_seconds,
        "effective_work_seconds": record.effective_work_seconds,
        "overtime_seconds": record.overtime_seconds,
        "within_geofence": within_geofence,
    }


# ── Lunch Breaks ──────────────────────────────────────────────────────────────

async def start_lunch(db: AsyncSession, employee_id: uuid.UUID) -> dict:
    """Start a lunch break."""
    now = datetime.now(timezone.utc)
    today_date = now.date()

    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            cast(AttendanceRecord.date, Date) == today_date,
        )
    )
    record = result.scalar_one_or_none()
    if not record or not record.check_in_time:
        return {"error": "Must check in before starting lunch"}
    if record.check_out_time:
        return {"error": "Already checked out for the day"}

    # Check for active lunch
    active_result = await db.execute(
        select(LunchBreakLog).where(
            LunchBreakLog.attendance_record_id == record.id,
            LunchBreakLog.ended_at.is_(None),
        )
    )
    active_lunch = active_result.scalar_one_or_none()
    if active_lunch:
        return {"error": "Lunch break already in progress", "started_at": active_lunch.started_at.isoformat()}

    lunch_log = LunchBreakLog(
        attendance_record_id=record.id,
        employee_id=employee_id,
        started_at=now,
    )
    db.add(lunch_log)
    await db.commit()
    await db.refresh(lunch_log)

    return {
        "success": True,
        "lunch_id": str(lunch_log.id),
        "started_at": lunch_log.started_at.isoformat(),
    }


async def end_lunch(db: AsyncSession, employee_id: uuid.UUID) -> dict:
    """End an active lunch break."""
    now = datetime.now(timezone.utc)
    today_date = now.date()

    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            cast(AttendanceRecord.date, Date) == today_date,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"error": "No attendance record found for today"}

    active_result = await db.execute(
        select(LunchBreakLog).where(
            LunchBreakLog.attendance_record_id == record.id,
            LunchBreakLog.ended_at.is_(None),
        )
    )
    lunch_log = active_result.scalar_one_or_none()
    if not lunch_log:
        return {"error": "No active lunch break found"}

    lunch_log.ended_at = now
    lunch_log.duration_seconds = int((now - lunch_log.started_at).total_seconds())

    await db.commit()
    await db.refresh(lunch_log)

    return {
        "success": True,
        "lunch_id": str(lunch_log.id),
        "ended_at": lunch_log.ended_at.isoformat(),
        "duration_seconds": lunch_log.duration_seconds,
    }


# ── Records Query ─────────────────────────────────────────────────────────────

async def get_today_overview(db: AsyncSession) -> dict:
    """Get today's attendance overview for the admin dashboard."""
    await auto_close_attendance_records(db)
    now = datetime.now(timezone.utc)
    today_date = now.date()

    # All records for today (cast to Date for robust comparison)
    result = await db.execute(
        select(AttendanceRecord).where(cast(AttendanceRecord.date, Date) == today_date)
    )
    records = list(result.scalars().all())

    # Get employee details
    emp_ids = [r.employee_id for r in records]
    emp_result = await db.execute(
        select(Employee).where(Employee.id.in_(emp_ids)) if emp_ids else select(Employee).where(False)
    )
    emp_map = {e.id: e for e in emp_result.scalars().all()}

    # Total active employees
    total_result = await db.execute(
        select(func.count(Employee.id)).where(Employee.is_active)
    )
    total_employees = total_result.scalar() or 0

    checked_in = sum(1 for r in records if r.check_in_time and not r.check_out_time)
    checked_out = sum(1 for r in records if r.check_out_time)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.late)
    on_lunch = 0

    # Map from attendance_record_id -> active LunchBreakLog
    lunch_active_map = {}
    active_lunches_res = await db.execute(
        select(LunchBreakLog).where(LunchBreakLog.ended_at.is_(None))
    )
    for log_item in active_lunches_res.scalars().all():
        lunch_active_map[log_item.attendance_record_id] = log_item

    on_lunch = 0
    for r in records:
        if r.id in lunch_active_map:
            on_lunch += 1

    present_count = sum(
        1 for r in records
        if r.status in (AttendanceStatus.present, AttendanceStatus.late)
    )
    absent_count = total_employees - len(records)

    # Get all locations to map IDs to names
    loc_result = await db.execute(select(AttendanceLocation))
    loc_map = {l.id: l.name for l in loc_result.scalars().all()}

    details = []
    for r in records:
        emp = emp_map.get(r.employee_id)
        active_lunch = lunch_active_map.get(r.id)
        details.append({
            "id": str(r.id),
            "employee_id": str(r.employee_id),
            "employee_name": emp.full_name if emp else "Unknown",
            "employee_email": emp.email if emp else "",
            "date": r.date.isoformat(),
            "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
            "check_out_time": r.check_out_time.isoformat() if r.check_out_time else None,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "check_in_count": r.check_in_count,
            "total_work_seconds": r.total_work_seconds,
            "effective_work_seconds": r.effective_work_seconds,
            "overtime_seconds": r.overtime_seconds,
            "within_geofence": r.check_in_within_geofence,
            "is_remote": r.is_remote,
            "notes": r.notes,
            "on_lunch": active_lunch is not None,
            "lunch_started_at": active_lunch.started_at.isoformat() if active_lunch else None,
            "check_in_location_name": loc_map.get(r.check_in_location_id) if r.check_in_location_id else None,
            "check_out_location_name": loc_map.get(r.check_out_location_id) if r.check_out_location_id else None,
        })


    return {
        "total_employees": total_employees,
        "checked_in": checked_in,
        "checked_out": checked_out,
        "present": present_count,
        "late": late_count,
        "absent": absent_count,
        "on_lunch": on_lunch,
        "records": details,
    }


async def get_records(
    db: AsyncSession,
    employee_id: Optional[uuid.UUID] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Get attendance records with filtering and pagination."""
    await auto_close_attendance_records(db)
    query = select(AttendanceRecord)
    count_query = select(func.count(AttendanceRecord.id))

    filters = []
    if employee_id:
        filters.append(AttendanceRecord.employee_id == employee_id)
    if date_from:
        dt_from = datetime.fromisoformat(date_from)
        if dt_from.tzinfo is None:
            dt_from = dt_from.replace(tzinfo=timezone.utc)
        filters.append(AttendanceRecord.date >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to)
        if dt_to.tzinfo is None:
            dt_to = dt_to.replace(tzinfo=timezone.utc)
        filters.append(AttendanceRecord.date <= dt_to)
    if status:
        filters.append(AttendanceRecord.status == AttendanceStatus(status))

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Sorting
    sort_col = getattr(AttendanceRecord, sort_by, AttendanceRecord.date)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    records = list(result.scalars().all())

    # Get employee names
    emp_ids = list(set(r.employee_id for r in records))
    emp_result = await db.execute(
        select(Employee).where(Employee.id.in_(emp_ids)) if emp_ids else select(Employee).where(False)
    )
    emp_map = {e.id: e for e in emp_result.scalars().all()}

    # Get all locations to map IDs to names
    loc_result = await db.execute(select(AttendanceLocation))
    loc_map = {l.id: l.name for l in loc_result.scalars().all()}

    items = []
    for r in records:
        emp = emp_map.get(r.employee_id)
        items.append({
            "id": str(r.id),
            "employee_id": str(r.employee_id),
            "employee_name": emp.full_name if emp else "Unknown",
            "employee_email": emp.email if emp else "",
            "date": r.date.isoformat(),
            "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
            "check_out_time": r.check_out_time.isoformat() if r.check_out_time else None,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "check_in_count": r.check_in_count,
            "total_work_seconds": r.total_work_seconds,
            "effective_work_seconds": r.effective_work_seconds,
            "overtime_seconds": r.overtime_seconds,
            "lunch_deducted_seconds": r.lunch_deducted_seconds,
            "check_in_within_geofence": r.check_in_within_geofence,
            "check_out_within_geofence": r.check_out_within_geofence,
            "is_remote": r.is_remote,
            "notes": r.notes,
            "check_in_location_name": loc_map.get(r.check_in_location_id) if r.check_in_location_id else None,
            "check_out_location_name": loc_map.get(r.check_out_location_id) if r.check_out_location_id else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


async def update_record(
    db: AsyncSession,
    record_id: uuid.UUID,
    data: dict,
) -> Optional[dict]:
    """Admin override: update a record's status, notes, times, or is_remote."""
    result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    if "status" in data:
        record.status = AttendanceStatus(data["status"])
    if "notes" in data:
        record.notes = data["notes"]
    if "is_remote" in data:
        record.is_remote = data["is_remote"]
    if "check_in_count" in data:
        record.check_in_count = data["check_in_count"]

    time_updated = False
    if "check_in_time" in data:
        val = data["check_in_time"]
        if val:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            record.check_in_time = dt
        else:
            record.check_in_time = None
        time_updated = True

    if "check_out_time" in data:
        val = data["check_out_time"]
        if val:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            record.check_out_time = dt
        else:
            record.check_out_time = None
        time_updated = True

    if time_updated or "is_remote" in data:
        # Recalculate work seconds
        if record.check_in_time and record.check_out_time:
            total_seconds = int((record.check_out_time - record.check_in_time).total_seconds())
            record.total_work_seconds = max(total_seconds, 0)
        else:
            record.total_work_seconds = 0

        # Get settings for lunch/overtime recalculations
        settings = await get_attendance_settings(db)
        
        lunch_deducted = 0
        if settings and settings.lunch_break_enabled and settings.auto_deduct_lunch:
            lunch_deducted = settings.lunch_break_duration_minutes * 60
        else:
            # Sum actual lunch break durations
            lunch_result = await db.execute(
                select(func.coalesce(func.sum(LunchBreakLog.duration_seconds), 0)).where(
                    LunchBreakLog.attendance_record_id == record.id,
                    LunchBreakLog.ended_at.isnot(None),
                )
            )
            lunch_deducted = lunch_result.scalar() or 0

        record.lunch_deducted_seconds = lunch_deducted
        record.effective_work_seconds = max(record.total_work_seconds - lunch_deducted, 0)

        # Update status/overtime based on settings
        if settings:
            effective_hours = record.effective_work_seconds / 3600
            # Only downgrade status if it is present or late (to avoid overwrite of leave/holiday status)
            if record.status in (AttendanceStatus.present, AttendanceStatus.late):
                if effective_hours < settings.half_day_threshold_hours:
                    record.status = AttendanceStatus.half_day
                else:
                    # check if late based on work_start_time
                    work_start = _parse_work_time(settings.work_start_time, record.check_in_time)
                    late_cutoff = work_start + timedelta(minutes=settings.late_threshold_minutes)
                    record.status = AttendanceStatus.present if record.check_in_time <= late_cutoff else AttendanceStatus.late

            # Overtime
            if settings.overtime_enabled:
                overtime_threshold = settings.overtime_after_hours * 3600
                if record.effective_work_seconds > overtime_threshold:
                    record.overtime_seconds = int(record.effective_work_seconds - overtime_threshold)
                else:
                    record.overtime_seconds = 0
            else:
                record.overtime_seconds = 0

    await db.commit()
    await db.refresh(record)

    emp_result = await db.execute(select(Employee).where(Employee.id == record.employee_id))
    emp = emp_result.scalar_one_or_none()

    return {
        "id": str(record.id),
        "employee_id": str(record.employee_id),
        "employee_name": emp.full_name if emp else "Unknown",
        "date": record.date.isoformat(),
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "check_in_count": record.check_in_count,
        "notes": record.notes,
        "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
        "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
        "total_work_seconds": record.total_work_seconds,
        "effective_work_seconds": record.effective_work_seconds,
        "overtime_seconds": record.overtime_seconds,
        "is_remote": record.is_remote,
    }


async def delete_record(db: AsyncSession, record_id: uuid.UUID) -> bool:
    """Delete an attendance record and all associated LunchBreakLog entries."""
    result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return False
    
    # Delete associated LunchBreakLog entries
    from sqlalchemy import delete
    await db.execute(
        delete(LunchBreakLog).where(LunchBreakLog.attendance_record_id == record_id)
    )
    
    # Delete record
    await db.delete(record)
    await db.commit()
    return True



async def get_stats(
    db: AsyncSession,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Attendance summary statistics for the admin dashboard."""
    now = datetime.now(timezone.utc)
    if not date_from:
        date_from = (now - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = now.isoformat()

    from_dt = datetime.fromisoformat(date_from)
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=timezone.utc)
    to_dt = datetime.fromisoformat(date_to)
    if to_dt.tzinfo is None:
        to_dt = to_dt.replace(tzinfo=timezone.utc)

    base = select(AttendanceRecord).where(
        AttendanceRecord.date >= from_dt,
        AttendanceRecord.date <= to_dt,
    )
    result = await db.execute(base)
    records = list(result.scalars().all())

    total_records = len(records)
    present_count = sum(1 for r in records if r.status == AttendanceStatus.present)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.late)
    half_day_count = sum(1 for r in records if r.status == AttendanceStatus.half_day)
    on_leave_count = sum(1 for r in records if r.status == AttendanceStatus.on_leave)

    avg_work_seconds = (
        sum(r.effective_work_seconds for r in records) / total_records
        if total_records > 0 else 0
    )
    total_overtime = sum(r.overtime_seconds for r in records)
    remote_count = sum(1 for r in records if r.is_remote)

    return {
        "period": {"from": date_from, "to": date_to},
        "total_records": total_records,
        "present": present_count,
        "late": late_count,
        "half_day": half_day_count,
        "on_leave": on_leave_count,
        "avg_work_seconds": int(avg_work_seconds),
        "total_overtime_seconds": total_overtime,
        "remote_checkins": remote_count,
        "on_time_percentage": round(present_count / total_records * 100, 1) if total_records > 0 else 0,
    }


async def auto_close_attendance_records(db: AsyncSession) -> None:
    """
    Finds open attendance records (check_out_time IS NULL) from today or past days.
    If a record is in the past, or today after work hours and the employee is offline,
    we close it and compute check-out details using their last activity timestamp.
    """
    now = datetime.now(timezone.utc)
    
    # Fetch all records with no check_out_time
    result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.check_out_time.is_(None))
    )
    open_records = list(result.scalars().all())
    if not open_records:
        return

    import zoneinfo
    from app.services.online_tracker import is_employee_online
    from app.models import Device, ActivityEvent, WorkSession, DeviceStatus

    for r in open_records:
        try:
            # Get employee details
            emp_res = await db.execute(select(Employee).where(Employee.id == r.employee_id))
            emp = emp_res.scalar_one_or_none()
            if not emp:
                continue

            work_end_hr = getattr(emp, "work_end_hour", 18)
            tz_str = getattr(emp, "timezone", "UTC")
            try:
                tz = zoneinfo.ZoneInfo(tz_str)
            except Exception:
                tz = timezone.utc

            local_now = now.astimezone(tz)
            record_local_date = r.date.astimezone(tz).date()
            today_local_date = local_now.date()

            is_past_day = record_local_date < today_local_date
            is_today_after_hours = (record_local_date == today_local_date) and (local_now.hour >= work_end_hr)

            should_checkout = False
            if is_past_day:
                should_checkout = True
            elif is_today_after_hours:
                # Check if employee is offline
                is_online = await is_employee_online(r.employee_id, db)
                if not is_online:
                    should_checkout = True

            if should_checkout:
                # Find checkout time based on latest activity on that day
                # Find latest heartbeat of approved devices
                dev_res = await db.execute(
                    select(Device.last_heartbeat)
                    .where(Device.employee_id == r.employee_id, Device.status == DeviceStatus.approved)
                    .order_by(Device.last_heartbeat.desc())
                    .limit(1)
                )
                last_hb = dev_res.scalar_one_or_none()

                # Find latest event timestamp
                ev_res = await db.execute(
                    select(ActivityEvent.timestamp)
                    .where(ActivityEvent.employee_id == r.employee_id)
                    .order_by(ActivityEvent.timestamp.desc())
                    .limit(1)
                )
                last_ev = ev_res.scalar_one_or_none()

                # Find latest work session end
                sess_res = await db.execute(
                    select(WorkSession.ended_at)
                    .where(WorkSession.employee_id == r.employee_id)
                    .order_by(WorkSession.ended_at.desc().nulls_last())
                    .limit(1)
                )
                last_sess = sess_res.scalar_one_or_none()

                candidates = [c for c in [last_hb, last_ev, last_sess, r.check_in_time] if c is not None]
                # Filter candidates to only be on the record date (or after check_in_time)
                valid_candidates = []
                for c in candidates:
                    # Make sure it's timezone-aware
                    if c.tzinfo is None:
                        c = c.replace(tzinfo=timezone.utc)
                    if c >= r.check_in_time:
                        valid_candidates.append(c)

                checkout_time = max(valid_candidates) if valid_candidates else now
                
                # Perform checkout updates
                r.check_out_time = checkout_time
                total_seconds = int((checkout_time - r.check_in_time).total_seconds())
                r.total_work_seconds = max(total_seconds, 0)

                settings = await get_attendance_settings(db)
                lunch_deducted = 0
                if settings and settings.lunch_break_enabled and settings.auto_deduct_lunch:
                    lunch_deducted = settings.lunch_break_duration_minutes * 60
                else:
                    lunch_result = await db.execute(
                        select(func.coalesce(func.sum(LunchBreakLog.duration_seconds), 0)).where(
                            LunchBreakLog.attendance_record_id == r.id,
                            LunchBreakLog.ended_at.isnot(None),
                        )
                    )
                    lunch_deducted = lunch_result.scalar() or 0

                r.lunch_deducted_seconds = lunch_deducted
                r.effective_work_seconds = max(r.total_work_seconds - lunch_deducted, 0)

                if settings:
                    effective_hours = r.effective_work_seconds / 3600
                    if r.status in (AttendanceStatus.present, AttendanceStatus.late):
                        if effective_hours < settings.half_day_threshold_hours:
                            r.status = AttendanceStatus.half_day
                        else:
                            # Re-verify if late
                            work_start = _parse_work_time(settings.work_start_time, r.check_in_time)
                            late_cutoff = work_start + timedelta(minutes=settings.late_threshold_minutes)
                            r.status = AttendanceStatus.present if r.check_in_time <= late_cutoff else AttendanceStatus.late

                    if settings.overtime_enabled:
                        overtime_threshold = settings.overtime_after_hours * 3600
                        if r.effective_work_seconds > overtime_threshold:
                            r.overtime_seconds = int(r.effective_work_seconds - overtime_threshold)
                        else:
                            r.overtime_seconds = 0
                    else:
                        r.overtime_seconds = 0

                db.add(r)
                log.info("attendance_record_auto_closed", employee_id=str(r.employee_id), record_id=str(r.id), checkout_time=checkout_time.isoformat())
        except Exception as e:
            log.warning(f"failed_to_auto_close_record record_id={r.id}: {e}")

    await db.commit()
