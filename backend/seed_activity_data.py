"""
Seed script: adds dummy activity data for the current week.
Run this to populate the database with test data for AI analysis.

Usage:
    python seed_activity_data.py
"""

import asyncio
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, ensure_schema_ready
from app.models import Employee, DailySummary, AnomalyLog, Department
import uuid


async def seed_activity_data():
    """Add dummy activity data for current week"""
    await ensure_schema_ready()

    async with AsyncSessionLocal() as db:
        # Get or create a department
        dept_result = await db.execute(select(Department).limit(1))
        department = dept_result.scalar_one_or_none()
        if not department:
            department = Department(
                id=uuid.uuid4(),
                name="Engineering",
                description="Engineering department"
            )
            db.add(department)
            await db.commit()
            print(f"✓ Created department: {department.name}")

        # Get or create employee "Aniket Nikam"
        emp_result = await db.execute(
            select(Employee).where(Employee.full_name == "Aniket Nikam")
        )
        employee = emp_result.scalars().first()
        
        from app.core.security import hash_password
        default_pwd_hash = hash_password("PulseDesk123!")

        if not employee:
            employee = Employee(
                id=uuid.uuid4(),
                email="aniket@pulsedesk.local",
                full_name="Aniket Nikam",
                department_id=department.id,
                job_title="Software Engineer",
                timezone="UTC",
                work_start_hour=9,
                work_end_hour=18,
                is_active=True,
                hashed_password=default_pwd_hash,
            )
            db.add(employee)
            await db.commit()
            print(f"✓ Created employee: {employee.full_name}")
        else:
            employee.hashed_password = default_pwd_hash
            await db.commit()
            print(f"[OK] Found existing employee: {employee.full_name} (updated password)")

        # Get current week (Mon-Sun or last 7 days)
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Monday of current week
        
        # Purge existing data for this employee to allow clean seeding
        from sqlalchemy import delete
        await db.execute(delete(DailySummary).where(DailySummary.employee_id == employee.id))
        await db.execute(delete(AnomalyLog).where(AnomalyLog.employee_id == employee.id))
        await db.commit()
        
        # List of apps to rotate through
        
        # Create activity data for each day this week
        for day_offset in range(7):
            current_date = start_of_week + timedelta(days=day_offset)
            
            # Skip if it's in the future
            if current_date > today:
                continue
            
            # Check if data already exists for this day
            existing = await db.execute(
                select(DailySummary).where(
                    (DailySummary.employee_id == employee.id) &
                    (DailySummary.date == current_date)
                )
            )
            if existing.scalar_one_or_none():
                print(f"⊘ Activity data already exists for {current_date}")
                continue
            
            # Create realistic activity data
            active_seconds = int(7.5 * 3600)  # 7.5 hours of active time
            idle_seconds = int(0.5 * 3600)    # 30 minutes idle
            focus_seconds = int(4.5 * 3600)   # 4.5 hours in focus
            
            # Vary by day of week - less activity on Friday
            if current_date.weekday() == 4:  # Friday
                active_seconds = int(6.5 * 3600)
                focus_seconds = int(3.5 * 3600)
            
            # Build hourly breakdown
            hourly_active = {}
            for hour in range(9, 18):  # 9 AM to 6 PM
                hourly_active[str(hour)] = 300 + (100 if hour in [10, 14, 15] else -50)
            
            # Build activity breakdown by category
            
            daily_summary = DailySummary(
                id=uuid.uuid4(),
                employee_id=employee.id,
                date=datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc),
                
                total_tracked_seconds=active_seconds + idle_seconds,
                active_seconds=active_seconds,
                idle_seconds=idle_seconds,
                focus_seconds=focus_seconds,
                
                productivity_score=0.75 + (0.05 if day_offset < 4 else -0.1),  # Drop on Thu/Fri
                focus_sessions=4,
                app_switches=12,
                top_app="VS Code",
                top_category="software_development",
                
                hourly_active_seconds=hourly_active,
                anomaly_count=1 if day_offset == 3 else 0,  # Anomaly on Thursday
                computed_at=datetime.now(timezone.utc),
            )
            
            # Store activity_breakdown as a string or property (if not in model, we'll skip it)
            # For now, store it in hourly_active_seconds or use JSON encoding
            db.add(daily_summary)
            
            print(f"✓ Created activity data for {current_date.strftime('%A, %B %d')}")
            print(f"  - Active: {active_seconds//3600}h {(active_seconds%3600)//60}m")
            print(f"  - Focus: {focus_seconds//3600}h {(focus_seconds%3600)//60}m")
            print(f"  - Productivity Score: {daily_summary.productivity_score:.2f}")
        
        await db.commit()
        print("\n✅ Activity data seeding complete!")
        print(f"✅ Ready for AI analysis on employee: {employee.full_name}")


if __name__ == "__main__":
    asyncio.run(seed_activity_data())
