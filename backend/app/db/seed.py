"""
Seed script: creates the first super admin account.
Run once after DB is initialized:
    python -m app.db.seed

Usage:
    ADMIN_EMAIL=admin@yourcompany.com ADMIN_PASSWORD=changeme python -m app.db.seed
"""

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, init_db
from app.models import Admin, UserRole
from app.core.security import hash_password


async def seed():
    await init_db()

    email = os.getenv("ADMIN_EMAIL", "admin@pulsedesk.local")
    password = os.getenv("ADMIN_PASSWORD", "changeme123!")
    full_name = os.getenv("ADMIN_NAME", "Super Admin")

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Admin).where(Admin.email == email))
        if existing.scalar_one_or_none():
            print(f"Admin already exists: {email}")
            return

        admin = Admin(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.super_admin,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print(f"✓ Super admin created: {email}")
        print(f"  Password: {password}")
        print(f"  IMPORTANT: Change this password immediately after first login.")


if __name__ == "__main__":
    asyncio.run(seed())
