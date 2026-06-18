"""
Screenshot Cleanup Service — Background task to purge screenshots older than the retention limit.
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import SystemSettings, Screenshot
from app.core.config import settings as app_settings
from app.core.files import safe_path_join
from app.core.logging import get_logger

log = get_logger("screenshot_cleanup")


async def clean_expired_screenshots():
    """Find and delete screenshots older than the retention threshold set in system settings."""
    now = datetime.now(timezone.utc)
    
    async with AsyncSessionLocal() as db:
        try:
            # Fetch screenshot retention settings
            result = await db.execute(select(SystemSettings))
            settings = result.scalar_one_or_none()
            
            # Default to 30 days retention if settings or value is missing
            retention_days = settings.screenshot_retention_days if settings else 30
            
            cutoff = now - timedelta(days=retention_days)
            
            # Find screenshots captured before cutoff
            query = select(Screenshot).where(Screenshot.captured_at < cutoff)
            db_result = await db.execute(query)
            expired_screenshots = db_result.scalars().all()
            
            if not expired_screenshots:
                return
                
            log.info("starting_screenshot_retention_cleanup", count=len(expired_screenshots), retention_days=retention_days)
            
            deleted_count = 0
            for shot in expired_screenshots:
                # Remove file from disk
                filepath = safe_path_join(app_settings.SCREENSHOT_DIR, shot.file_path)
                if filepath.exists():
                    try:
                        os.remove(filepath)
                        log.debug("screenshot_file_deleted", file=shot.file_path)
                    except OSError as e:
                        log.error("cleanup_screenshot_file_failed", file_path=shot.file_path, error=str(e))
                
                # ✅ Delete DB record using async-safe SQLAlchemy delete
                from sqlalchemy import delete
                await db.execute(delete(Screenshot).where(Screenshot.id == shot.id))
                deleted_count += 1
                
            await db.commit()
            log.info("completed_screenshot_retention_cleanup", deleted_count=deleted_count)
            
        except Exception as e:
            log.error("screenshot_retention_cleanup_failed", error=str(e))
            await db.rollback()


async def screenshot_cleanup_loop():
    """Periodic loop that executes the cleanup query every hour."""
    log.info("screenshot_cleanup_loop_started")
    while True:
        try:
            await clean_expired_screenshots()
        except Exception as e:
            log.error("screenshot_cleanup_loop_error", error=str(e))
        # Run cleanup every hour (3600 seconds)
        await asyncio.sleep(3600)


def start_screenshot_cleanup_task():
    """Starts the cleanup background task."""
    loop = asyncio.get_event_loop()
    loop.create_task(screenshot_cleanup_loop())
