"""
Break Alert Service — Background service to monitor active breaks and trigger alerts.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models import (
    LunchBreakLog, Employee, AttendanceRecord,
    AnomalyLog, AnomalyType, Device
)
from app.services.ws_broadcaster import broadcast_break_alert
from app.core.logging import get_logger

log = get_logger("break_alerts")


async def check_active_breaks():
    """Check all currently active breaks and alert if duration exceeds limits."""
    now = datetime.now(timezone.utc)
    
    async with AsyncSessionLocal() as db:
        # Get settings
        from app.services.attendance_service import get_attendance_settings
        settings = await get_attendance_settings(db)
        if not settings or not settings.break_alert_enabled:
            return

        # Query active breaks (ended_at IS NULL)
        query = select(LunchBreakLog, Employee, AttendanceRecord).join(
            Employee, Employee.id == LunchBreakLog.employee_id
        ).join(
            AttendanceRecord, AttendanceRecord.id == LunchBreakLog.attendance_record_id
        ).where(
            LunchBreakLog.ended_at.is_(None)
        )
        
        result = await db.execute(query)
        active_items = result.all()
        
        for break_log, employee, record in active_items:
            elapsed_minutes = (now - break_log.started_at).total_seconds() / 60.0
            allowed_minutes = settings.lunch_break_duration_minutes
            grace_minutes = settings.break_alert_grace_minutes
            threshold = allowed_minutes + grace_minutes
            
            if elapsed_minutes > threshold:
                # Check cooldown: has this employee been alerted of excessive break in last 15 mins?
                cooldown_since = now - timedelta(minutes=15)
                already_alerted_query = select(func.count(AnomalyLog.id)).where(
                    AnomalyLog.employee_id == employee.id,
                    AnomalyLog.anomaly_type == AnomalyType.excessive_break,
                    AnomalyLog.detected_at >= cooldown_since
                )
                
                cooldown_result = await db.execute(already_alerted_query)
                if (cooldown_result.scalar() or 0) > 0:
                    continue

                # Find employee's device
                device_query = select(Device).where(
                    Device.employee_id == employee.id,
                    Device.status == "approved"
                ).order_by(Device.last_heartbeat.desc().nulls_last())
                device_result = await db.execute(device_query)
                device = device_result.scalars().first()
                if not device:
                    # Fallback to any device
                    device_query = select(Device).where(Device.employee_id == employee.id)
                    device_result = await db.execute(device_query)
                    device = device_result.scalars().first()
                
                if not device:
                    # Can't create anomaly log without device_id
                    log.warning("no_device_for_break_alert", employee_id=str(employee.id))
                    continue

                # Create AnomalyLog
                exceeded_by = int(elapsed_minutes - allowed_minutes)
                description = f"{employee.full_name} has exceeded lunch break by {exceeded_by} minutes (Limit: {allowed_minutes} min)."
                
                anomaly = AnomalyLog(
                    employee_id=employee.id,
                    device_id=device.id,
                    anomaly_type=AnomalyType.excessive_break,
                    description=description,
                    event_metadata={
                        "lunch_break_log_id": str(break_log.id),
                        "elapsed_minutes": int(elapsed_minutes),
                        "allowed_minutes": allowed_minutes,
                        "grace_minutes": grace_minutes,
                        "severity": "medium",
                    }
                )
                db.add(anomaly)
                
                try:
                    await db.commit()
                except Exception as e:
                    log.error("break_alert_commit_failed", error=str(e))
                    await db.rollback()
                    continue

                # Broadcast WS alert
                try:
                    await broadcast_break_alert({
                        "employee_id": str(employee.id),
                        "employee_name": employee.full_name,
                        "elapsed_minutes": int(elapsed_minutes),
                        "allowed_minutes": allowed_minutes,
                        "description": description,
                        "detected_at": now.isoformat(),
                    })
                    log.info("break_alert_triggered", employee_id=str(employee.id), elapsed=int(elapsed_minutes))
                except Exception as e:
                    log.warning("break_alert_broadcast_failed", error=str(e))


async def break_alert_checker_loop():
    """Background loop to check breaks every 60 seconds."""
    log.info("break_alert_checker_started")
    while True:
        try:
            await check_active_breaks()
        except Exception as e:
            log.error("break_alert_checker_loop_error", error=str(e))
        await asyncio.sleep(60)


def start_break_alert_checker():
    """Start the background checker task."""
    loop = asyncio.get_event_loop()
    loop.create_task(break_alert_checker_loop())
