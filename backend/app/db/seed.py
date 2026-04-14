"""
Seed script: creates the first super admin account.
Run once after DB is initialized:
    python -m app.db.seed

Usage:
    ADMIN_EMAIL=admin@yourcompany.com ADMIN_PASSWORD=<strong-password> python -m app.db.seed
"""

import asyncio
import os

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, ensure_schema_ready
from app.models import Admin, UserRole
from app.core.security import hash_password


async def seed():
    await ensure_schema_ready()

    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    full_name = os.getenv("ADMIN_NAME", "Super Admin").strip()

    if not email or not password:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be set to create initial admin")
    if len(password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")
    if "changeme" in password.lower():
        raise RuntimeError("ADMIN_PASSWORD must not contain insecure placeholder values")

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
        print("  Password not echoed for security.")


if __name__ == "__main__":
    asyncio.run(seed())
