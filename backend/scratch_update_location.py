import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import AttendanceLocation

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AttendanceLocation).where(AttendanceLocation.name == "Home"))
        loc = res.scalar_one_or_none()
        if loc:
            loc.latitude = 19.0748
            loc.longitude = 72.8856
            loc.radius_meters = 2000  # make radius larger just in case (2km)
            await db.commit()
            print(f"Updated geofence '{loc.name}' coordinates to {loc.latitude}, {loc.longitude} with radius {loc.radius_meters}m")
        else:
            print("Geofence location 'Home' not found.")

if __name__ == "__main__":
    asyncio.run(main())
