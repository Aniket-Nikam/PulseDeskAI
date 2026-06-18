import asyncio
import os
import sys
from sqlalchemy import select

# Set up python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import AsyncSessionLocal
from app.models import Employee, Department
from app.api.v1.routes.analytics import get_live_overview

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Employee, Department.name.label("dept_name"))
            .outerjoin(Department, Employee.department_id == Department.id)
        )
        rows = res.all()
        print("Employee is_active status:")
        for emp, dept in rows:
            print(f"  Name: {emp.full_name}")
            print(f"    ID: {emp.id}")
            print(f"    is_active: {emp.is_active}")
            print(f"    department: {dept}")

        print("\nTesting get_live_overview endpoint results:")
        # Mock admin dependency
        overview_data = await get_live_overview(admin=None, db=db)
        print(f"Overview returned {len(overview_data)} employees:")
        for item in overview_data:
            print(f"  Name: {item['employee_name']}")
            print(f"    is_online: {item['is_online']}")
            print(f"    last_seen: {item['last_seen']}")
            print(f"    active_app: {item['active_app']}")

if __name__ == "__main__":
    asyncio.run(main())
