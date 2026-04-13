"""Reset admin password to changeme123."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def reset_password():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.core.security import hash_password
    
    new_hash = hash_password("changeme123")
    engine = create_async_engine("postgresql+asyncpg://postgres:123456@localhost:5432/pulsedesk")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE admins SET hashed_password = :pw WHERE email = 'admin@company.com'"),
            {"pw": new_hash},
        )
        print("Password reset to 'changeme123' for admin@company.com")
    await engine.dispose()

asyncio.run(reset_password())
