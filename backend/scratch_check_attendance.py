import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import AttendanceRecord, Employee

async def main():
    async with AsyncSessionLocal() as db:
        res_emp = await db.execute(select(Employee).where(Employee.email == "aniket@pulsedesk.local"))
        emp = res_emp.scalar_one_or_none()
        if not emp:
            print("Employee not found!")
            return
            
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        res_att = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp.id,
                AttendanceRecord.date == today,
            )
        )
        record = res_att.scalar_one_or_none()
        
        print(f"Attendance for {emp.full_name} ({emp.email}) on {today.date()}:")
        if record:
            print(f"- Checked In: {record.check_in_time}")
            print(f"- Latitude: {record.check_in_latitude}")
            print(f"- Longitude: {record.check_in_longitude}")
            print(f"- Status: {record.status}")
            print(f"- Within Geofence: {record.check_in_within_geofence}")
        else:
            print("- No attendance record found for today.")

if __name__ == "__main__":
    asyncio.run(main())
