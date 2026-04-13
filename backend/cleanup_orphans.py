"""Clean up screenshot DB records that have missing files on disk."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_DIR = "./screenshots"

async def cleanup():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    engine = create_async_engine("postgresql+asyncpg://postgres:123456@localhost:5432/pulsedesk")
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id, file_path FROM screenshots")
        )
        rows = result.fetchall()
        
        missing_ids = []
        for row in rows:
            filepath = os.path.join(SCREENSHOT_DIR, row[1])
            if not os.path.exists(filepath):
                missing_ids.append(str(row[0]))
        
        if missing_ids:
            print(f"Deleting {len(missing_ids)} orphan screenshot records (files missing on disk)...")
            # Delete in batches
            for mid in missing_ids:
                await conn.execute(
                    text("DELETE FROM screenshots WHERE id = :id"),
                    {"id": mid},
                )
            print(f"Done. Removed {len(missing_ids)} orphan records.")
        else:
            print("No orphan records found. All files exist on disk.")
    await engine.dispose()

asyncio.run(cleanup())
