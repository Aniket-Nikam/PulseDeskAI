import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import AttendanceLocation, AttendanceSettings

async def main():
    async with AsyncSessionLocal() as db:
        res_locs = await db.execute(select(AttendanceLocation))
        locs = res_locs.scalars().all()
        print("Geofence Locations:")
        for loc in locs:
            print(f"- Name: {loc.name}, Lat: {loc.latitude}, Lon: {loc.longitude}, Radius: {loc.radius_meters}m, Active: {loc.is_active}")
            
        res_sett = await db.execute(select(AttendanceSettings))
        settings = res_sett.scalar_one_or_none()
        if settings:
            print("\nAttendance Settings:")
            print(f"- Configured: {settings.is_configured}")
            print(f"- Allow Remote: {settings.allow_remote_checkin}")
            print(f"- Mode: {settings.mode}")
        else:
            print("\nAttendance Settings not configured.")

if __name__ == "__main__":
    asyncio.run(main())
