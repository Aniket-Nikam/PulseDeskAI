import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import hash_password
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def reset_password() -> None:
    from app.core.config import settings

    new_hash = hash_password("adminadmin123")
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE admins SET hashed_password = :pw WHERE email = :email"),
            {"pw": new_hash, "email": "admin@pulsedesk.com"},
        )
        if result.rowcount == 0:
            import uuid
            from datetime import datetime, timezone
            await conn.execute(
                text("INSERT INTO admins (id, email, hashed_password, full_name, role, is_active, created_at, updated_at) VALUES (:id, :email, :pw, :name, 'super_admin', true, :now, :now)"),
                {"id": str(uuid.uuid4()), "pw": new_hash, "email": "admin@pulsedesk.com", "name": "Admin", "now": datetime.now(timezone.utc)},
            )
            print("Admin inserted.")
        else:
            print(f"Password reset completed for: admin@pulsedesk.com")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_password())
