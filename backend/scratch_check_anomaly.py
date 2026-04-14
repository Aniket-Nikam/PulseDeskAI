import asyncio
from app.db.session import AsyncSessionLocal
from app.models import Employee, AnomalyLog
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Employee).where(Employee.full_name.in_(['Kaajal Rai', 'Nikam Aniket', 'Aniket Nikam'])))
        employees = res.scalars().all()
        for e in employees:
            print(f'Employee: {e.full_name}, ID: {e.id}, Is_active: {e.is_active}, StartHr: {getattr(e, "work_start_hour", 9)}, EndHr: {getattr(e, "work_end_hour", 18)}, TZ: {getattr(e, "timezone", "UTC")}')
            anom_res = await db.execute(select(AnomalyLog).where(AnomalyLog.employee_id == e.id))
            anoms = anom_res.scalars().all()
            print(f'  Anomalies count: {len(anoms)}')
            for a in anoms:
                print(f'  - {a.anomaly_type}: {a.description}')

asyncio.run(main())
