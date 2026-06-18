"""Check all screenshots in DB and verify files exist on disk."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_DIR = "./screenshots"


async def check():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    engine = create_async_engine("postgresql+asyncpg://postgres:123456@localhost:5432/pulsedesk")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT s.id, s.employee_id, s.file_path, s.file_size_bytes, e.full_name, s.captured_at
                FROM screenshots s 
                LEFT JOIN employees e ON s.employee_id = e.id 
                ORDER BY s.captured_at DESC
            """)
        )
        rows = result.fetchall()
        
        print(f"Total screenshots in DB: {len(rows)}")
        missing = 0
        found = 0
        for row in rows:
            filepath = os.path.join(SCREENSHOT_DIR, row[2])
            exists = os.path.exists(filepath)
            if not exists:
                missing += 1
                print(f"  [MISSING] id={row[0]}, emp={row[4]}, file={row[2]}, date={row[5]}")
            else:
                found += 1
                
        print(f"\nSummary: {found} files found, {missing} files MISSING")
        
        # Also list files on disk not in DB
        print("\n--- Files on disk ---")
        disk_files = set(os.listdir(SCREENSHOT_DIR)) if os.path.exists(SCREENSHOT_DIR) else set()
        db_files = {row[2] for row in rows}
        orphans = disk_files - db_files
        if orphans:
            print(f"  {len(orphans)} orphan files on disk (not in DB)")
        else:
            print(f"  All {len(disk_files)} disk files have DB records")
    await engine.dispose()

asyncio.run(check())
