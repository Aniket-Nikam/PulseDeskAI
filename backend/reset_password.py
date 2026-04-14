"""Reset an admin password using environment variables.

Required env:
  DATABASE_URL
  RESET_ADMIN_EMAIL
  RESET_ADMIN_PASSWORD
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def reset_password() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.security import hash_password

    database_url = os.getenv("DATABASE_URL", "").strip()
    admin_email = os.getenv("RESET_ADMIN_EMAIL", "").strip().lower()
    new_password = os.getenv("RESET_ADMIN_PASSWORD", "")

    if not database_url or not admin_email or not new_password:
        raise RuntimeError("DATABASE_URL, RESET_ADMIN_EMAIL, and RESET_ADMIN_PASSWORD are required")
    if len(new_password) < 12:
        raise RuntimeError("RESET_ADMIN_PASSWORD must be at least 12 characters")

    new_hash = hash_password(new_password)
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE admins SET hashed_password = :pw WHERE email = :email"),
            {"pw": new_hash, "email": admin_email},
        )
        print(f"Updated rows: {result.rowcount}")
        if result.rowcount == 0:
            print("No admin found for the given email.")
        else:
            print(f"Password reset completed for: {admin_email}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_password())
