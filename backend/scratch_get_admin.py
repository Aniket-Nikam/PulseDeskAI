import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Admin

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Admin))
        admins = result.scalars().all()
        print("Admins in DB:")
        for admin in admins:
            print(f"- Email: {admin.email}, Name: {admin.full_name}, Active: {admin.is_active}")

if __name__ == "__main__":
    asyncio.run(main())
