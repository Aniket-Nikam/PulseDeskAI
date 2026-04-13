#!/usr/bin/env python3
"""
Seed ActivityEvent and AppUsageDaily tables for Analytics dashboard
"""
import sys
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import uuid

# Setup path
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, delete
    from app.core.config import settings
    from app.models import Employee, Device, ActivityEvent, AppUsageDaily, ActivityType, DeviceStatus
    
    # Create engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get employee
        result = await session.execute(select(Employee).where(Employee.full_name == "Aniket Nikam"))
        employee = result.scalar_one_or_none()
        
        if not employee:
            print("❌ Employee 'Aniket Nikam' not found!")
            return
        
        print(f"✓ Found employee: {employee.full_name}")
        
        # Get or create device for employee
        device_result = await session.execute(
            select(Device).where(Device.employee_id == employee.id).limit(1)
        )
        device = device_result.scalar_one_or_none()
        
        if not device:
            # Create a device if none exists
            device = Device(
                id=uuid.uuid4(),
                employee_id=employee.id,
                hostname="LAPTOP-ANIKET",
                platform="Windows",
                os_version="11",
                agent_version="1.0.0",
                device_token=str(uuid.uuid4()),
                status=DeviceStatus.approved,
                enrolled_at=datetime.now(timezone.utc),
            )
            session.add(device)
            await session.commit()
            print(f"✓ Created device: {device.hostname}")
        else:
            print(f"✓ Found existing device: {device.hostname}")
        
        # Clear existing data
        await session.execute(delete(AppUsageDaily).where(AppUsageDaily.employee_id == employee.id))
        await session.execute(delete(ActivityEvent).where(ActivityEvent.employee_id == employee.id))
        await session.commit()
        
        # Generate data for last 7 days
        base_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        for day_offset in range(7):
            current_date = base_date - timedelta(days=day_offset)
            
            # === ActivityEvent Data ===
            # Generate activity events throughout the day
            activities = [
                # Morning session
                {"start_hour": 8, "start_min": 0, "duration_min": 120, "app": "VSCode", "category": "Development", "keystrokes": 450},
                {"start_hour": 10, "start_min": 15, "duration_min": 15, "app": "Chrome", "category": "Social", "keystrokes": 50},
                {"start_hour": 10, "start_min": 30, "duration_min": 90, "app": "VSCode", "category": "Development", "keystrokes": 380},
                
                # Lunch break
                {"start_hour": 12, "start_min": 30, "duration_min": 45, "app": "Spotify", "category": "Entertainment", "keystrokes": 0},
                
                # Afternoon session
                {"start_hour": 13, "start_min": 15, "duration_min": 60, "app": "Slack", "category": "Communication", "keystrokes": 120},
                {"start_hour": 14, "start_min": 15, "duration_min": 120, "app": "VSCode", "category": "Development", "keystrokes": 520},
                {"start_hour": 16, "start_min": 15, "duration_min": 30, "app": "Figma", "category": "Design", "keystrokes": 80},
                {"start_hour": 16, "start_min": 45, "duration_min": 90, "app": "VSCode", "category": "Development", "keystrokes": 400},
                
                # Evening
                {"start_hour": 18, "start_min": 15, "duration_min": 30, "app": "Outlook", "category": "Communication", "keystrokes": 60},
            ]
            
            for activity in activities:
                event_time = current_date.replace(
                    hour=activity["start_hour"],
                    minute=activity["start_min"]
                )
                
                event = ActivityEvent(
                    id=uuid.uuid4(),
                    device_id=device.id,
                    employee_id=employee.id,
                    timestamp=event_time,
                    activity_type=ActivityType.active,
                    active_app=activity["app"],
                    active_window_title=f"Working in {activity['app']}",
                    app_category=activity["category"],
                    keystrokes=activity["keystrokes"],
                    mouse_clicks=activity["keystrokes"] // 2,
                    mouse_distance_px=activity["keystrokes"] * 50,
                    idle_duration_seconds=0,
                    sample_duration_seconds=30,
                )
                session.add(event)
            
            # Add idle time events
            idle_times = [
                {"start_hour": 9, "duration_min": 15},  # Mid-morning
                {"start_hour": 11, "duration_min": 30},  # Late morning
                {"start_hour": 15, "duration_min": 15},  # Mid afternoon
                {"start_hour": 17, "duration_min": 30},  # Late afternoon
            ]
            
            for idle in idle_times:
                idle_time = current_date.replace(hour=idle["start_hour"])
                event = ActivityEvent(
                    id=uuid.uuid4(),
                    device_id=device.id,
                    employee_id=employee.id,
                    timestamp=idle_time,
                    activity_type=ActivityType.idle,
                    active_app="System Idle",
                    active_window_title="Idle",
                    app_category="Idle",
                    keystrokes=0,
                    mouse_clicks=0,
                    mouse_distance_px=0,
                    idle_duration_seconds=idle["duration_min"] * 60,
                    sample_duration_seconds=30,
                )
                session.add(event)
            
            # === AppUsageDaily Data ===
            apps = [
                {"name": "VSCode", "category": "Development", "total_sec": 5.5 * 3600, "active_sec": 5.5 * 3600},
                {"name": "Slack", "category": "Communication", "total_sec": 2.0 * 3600, "active_sec": 1.5 * 3600},
                {"name": "Chrome", "category": "Social", "total_sec": 1.5 * 3600, "active_sec": 0.8 * 3600},
                {"name": "Outlook", "category": "Communication", "total_sec": 0.5 * 3600, "active_sec": 0.3 * 3600},
            ]
            
            for app in apps:
                app_usage = AppUsageDaily(
                    id=uuid.uuid4(),
                    employee_id=employee.id,
                    date=current_date,
                    app_name=app["name"],
                    app_category=app["category"],
                    total_seconds=int(app["total_sec"]),
                    active_seconds=int(app["active_sec"]),
                    session_count=1,
                )
                session.add(app_usage)
            
            print(f"✓ Created activity & app data for {current_date.strftime('%A, %B %d')}")
        
        # Commit all changes
        await session.commit()
        print("\n✅ Analytics data seeding complete!")
        print(f"✅ ActivityEvent and AppUsageDaily tables populated for: {employee.full_name}")

if __name__ == "__main__":
    asyncio.run(main())
