"""
Attendance API Routes — Location-based attendance with employee/student mode.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.services import attendance_service
from app.core.logging import get_logger

router = APIRouter(prefix="/attendance", tags=["attendance"])
log = get_logger("attendance_routes")


# ── Schemas ───────────────────────────────────────────────────────────────────

class AttendanceSetupRequest(BaseModel):
    mode: str = Field(..., pattern="^(employee|student|both)$")


class AttendanceSettingsUpdate(BaseModel):
    mode: Optional[str] = Field(default=None, pattern="^(employee|student|both)$")
    work_start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    work_end_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    lunch_break_enabled: Optional[bool] = None
    lunch_break_start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    lunch_break_duration_minutes: Optional[int] = Field(default=None, ge=15, le=120)
    auto_deduct_lunch: Optional[bool] = None
    late_threshold_minutes: Optional[int] = Field(default=None, ge=1, le=120)
    early_checkout_threshold_minutes: Optional[int] = Field(default=None, ge=5, le=120)
    half_day_threshold_hours: Optional[float] = Field(default=None, ge=1.0, le=8.0)
    overtime_enabled: Optional[bool] = None
    overtime_after_hours: Optional[float] = Field(default=None, ge=4.0, le=16.0)
    require_location_for_checkout: Optional[bool] = None
    allow_remote_checkin: Optional[bool] = None
    break_alert_enabled: Optional[bool] = None
    break_alert_grace_minutes: Optional[int] = Field(default=None, ge=0, le=60)



class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meters: int = Field(default=200, ge=50, le=10000)
    applies_to: str = Field(default="all", pattern="^(all|employee|student)$")
    department_id: Optional[uuid.UUID] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    radius_meters: Optional[int] = Field(default=None, ge=50, le=10000)
    applies_to: Optional[str] = Field(default=None, pattern="^(all|employee|student)$")
    is_active: Optional[bool] = None
    department_id: Optional[uuid.UUID] = None


class CheckInRequest(BaseModel):
    employee_id: uuid.UUID
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class CheckOutRequest(BaseModel):
    employee_id: uuid.UUID
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class LunchRequest(BaseModel):
    employee_id: uuid.UUID


class RecordUpdate(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(present|late|half_day|absent|on_leave|holiday)$")
    notes: Optional[str] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    is_remote: Optional[bool] = None
    check_in_count: Optional[int] = None


# ── Settings endpoints ────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Get attendance settings. Returns null if not configured yet."""
    settings = await attendance_service.get_attendance_settings(db)
    if not settings:
        return {"configured": False}

    return {
        "configured": settings.is_configured,
        "mode": settings.mode.value if hasattr(settings.mode, "value") else str(settings.mode),
        "work_start_time": settings.work_start_time,
        "work_end_time": settings.work_end_time,
        "lunch_break_enabled": settings.lunch_break_enabled,
        "lunch_break_start_time": settings.lunch_break_start_time,
        "lunch_break_duration_minutes": settings.lunch_break_duration_minutes,
        "auto_deduct_lunch": settings.auto_deduct_lunch,
        "late_threshold_minutes": settings.late_threshold_minutes,
        "early_checkout_threshold_minutes": settings.early_checkout_threshold_minutes,
        "half_day_threshold_hours": settings.half_day_threshold_hours,
        "overtime_enabled": settings.overtime_enabled,
        "overtime_after_hours": settings.overtime_after_hours,
        "require_location_for_checkout": settings.require_location_for_checkout,
        "allow_remote_checkin": settings.allow_remote_checkin,
        "break_alert_enabled": settings.break_alert_enabled,
        "break_alert_grace_minutes": settings.break_alert_grace_minutes,
    }


@router.post("/setup")
async def setup(
    payload: AttendanceSetupRequest,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Initial setup: choose employee/student/both mode."""
    settings = await attendance_service.setup_attendance(db, payload.mode, admin.id)
    return {
        "configured": True,
        "mode": settings.mode.value if hasattr(settings.mode, "value") else str(settings.mode),
        "message": f"Attendance system configured for {payload.mode} mode",
    }


@router.put("/settings")
async def update_settings(
    payload: AttendanceSettingsUpdate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Update attendance settings."""
    data = payload.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        settings = await attendance_service.update_attendance_settings(db, data, admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "configured": settings.is_configured,
        "mode": settings.mode.value if hasattr(settings.mode, "value") else str(settings.mode),
        "work_start_time": settings.work_start_time,
        "work_end_time": settings.work_end_time,
        "lunch_break_enabled": settings.lunch_break_enabled,
        "lunch_break_start_time": settings.lunch_break_start_time,
        "lunch_break_duration_minutes": settings.lunch_break_duration_minutes,
        "auto_deduct_lunch": settings.auto_deduct_lunch,
        "late_threshold_minutes": settings.late_threshold_minutes,
        "early_checkout_threshold_minutes": settings.early_checkout_threshold_minutes,
        "half_day_threshold_hours": settings.half_day_threshold_hours,
        "overtime_enabled": settings.overtime_enabled,
        "overtime_after_hours": settings.overtime_after_hours,
        "require_location_for_checkout": settings.require_location_for_checkout,
        "allow_remote_checkin": settings.allow_remote_checkin,
        "break_alert_enabled": settings.break_alert_enabled,
        "break_alert_grace_minutes": settings.break_alert_grace_minutes,
    }


# ── Location endpoints ────────────────────────────────────────────────────────

@router.get("/locations")
async def list_locations(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """List all attendance geofence locations."""
    locations = await attendance_service.list_locations(db)
    return [
        {
            "id": str(loc.id),
            "name": loc.name,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "radius_meters": loc.radius_meters,
            "is_active": loc.is_active,
            "applies_to": loc.applies_to,
            "department_id": str(loc.department_id) if loc.department_id else None,
            "created_at": loc.created_at.isoformat() if loc.created_at else None,
        }
        for loc in locations
    ]


@router.post("/locations", status_code=201)
async def create_location(
    payload: LocationCreate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Add a new geofence location."""
    loc = await attendance_service.create_location(
        db,
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_meters=payload.radius_meters,
        applies_to=payload.applies_to,
        department_id=payload.department_id,
        admin_id=admin.id,
    )
    return {
        "id": str(loc.id),
        "name": loc.name,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "radius_meters": loc.radius_meters,
        "is_active": loc.is_active,
        "applies_to": loc.applies_to,
    }


@router.put("/locations/{location_id}")
async def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Update a geofence location."""
    data = payload.model_dump(exclude_none=True)
    loc = await attendance_service.update_location(db, location_id, data)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return {
        "id": str(loc.id),
        "name": loc.name,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "radius_meters": loc.radius_meters,
        "is_active": loc.is_active,
        "applies_to": loc.applies_to,
    }


@router.delete("/locations/{location_id}")
async def delete_location(
    location_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Remove a geofence location."""
    deleted = await attendance_service.delete_location(db, location_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Location not found")
    return {"message": "Location deleted"}


# ── Check-in / Check-out ─────────────────────────────────────────────────────

@router.post("/check-in")
async def do_check_in(
    payload: CheckInRequest,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Process a check-in with location validation."""
    result = await attendance_service.check_in(
        db, payload.employee_id, payload.latitude, payload.longitude,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/check-out")
async def do_check_out(
    payload: CheckOutRequest,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Process a check-out with location validation."""
    result = await attendance_service.check_out(
        db, payload.employee_id, payload.latitude, payload.longitude,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Lunch break ───────────────────────────────────────────────────────────────

@router.post("/lunch/start")
async def start_lunch(
    payload: LunchRequest,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Start a lunch break."""
    result = await attendance_service.start_lunch(db, payload.employee_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/lunch/end")
async def end_lunch(
    payload: LunchRequest,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """End a lunch break."""
    result = await attendance_service.end_lunch(db, payload.employee_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Records ───────────────────────────────────────────────────────────────────

@router.get("/today")
async def get_today(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Today's live attendance overview."""
    return await attendance_service.get_today_overview(db)


@router.get("/records")
async def get_records(
    employee_id: Optional[uuid.UUID] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    sort_by: str = Query(default="date"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated attendance records with sorting and filtering."""
    return await attendance_service.get_records(
        db,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.put("/records/{record_id}")
async def update_record(
    record_id: uuid.UUID,
    payload: RecordUpdate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Admin override: update status, notes, or times on an attendance record."""
    data = payload.model_dump(exclude_none=True)
    result = await attendance_service.update_record(db, record_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Record not found")
    
    from app.core.audit import log_admin_action
    log_admin_action(
        "UPDATE_ATTENDANCE_RECORD",
        admin_id=str(admin.id),
        employee_id=str(result["employee_id"]),
        record_id=str(record_id),
        updated_fields=list(data.keys()),
    )
    return result


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Admin override: delete an attendance record."""
    from sqlalchemy import select
    from app.models import AttendanceRecord
    rec_res = await db.execute(select(AttendanceRecord).where(AttendanceRecord.id == record_id))
    record = rec_res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    emp_id = str(record.employee_id)
    
    deleted = await attendance_service.delete_record(db, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
        
    from app.core.audit import log_admin_action
    log_admin_action(
        "DELETE_ATTENDANCE_RECORD",
        admin_id=str(admin.id),
        employee_id=emp_id,
        record_id=str(record_id),
    )
    return {"message": "Record deleted successfully"}


@router.get("/stats")
async def get_stats(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Attendance statistics summary."""
    return await attendance_service.get_stats(db, date_from=date_from, date_to=date_to)


@router.get("/export")
async def export_records(
    employee_id: Optional[uuid.UUID] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Export matching attendance records to a CSV file."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    records_data = await attendance_service.get_records(
        db,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        page=1,
        page_size=100000,
    )
    records = records_data.get("items", [])

    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Employee Name", "Employee Email", "Date", "Check-in Time", 
        "Check-out Time", "Status", "Work Hours", "Overtime Hours", 
        "Within Geofence (Check-in)", "Within Geofence (Check-out)", 
        "Is Remote", "Notes"
    ])

    for r in records:
        ci_str = r.get("check_in_time")
        co_str = r.get("check_out_time")
        
        work_secs = r.get("total_work_seconds") or 0
        work_hours = round(work_secs / 3600, 2)
        
        ot_secs = r.get("overtime_seconds") or 0
        ot_hours = round(ot_secs / 3600, 2)

        writer.writerow([
            r.get("employee_name"),
            r.get("employee_email"),
            r.get("date")[:10] if r.get("date") else "",
            ci_str[11:19] if ci_str else "",
            co_str[11:19] if co_str else "",
            r.get("status"),
            work_hours,
            ot_hours,
            "Yes" if r.get("check_in_within_geofence") else "No",
            "Yes" if r.get("check_out_within_geofence") else "No",
            "Yes" if r.get("is_remote") else "No",
            r.get("notes") or "",
        ])

    output.seek(0)
    filename = f"attendance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(output, media_type="text/csv", headers=headers)

