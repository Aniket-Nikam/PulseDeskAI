from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models import SystemSettings
from app.api.v1.routes.auth import require_admin_read, require_admin_write

router = APIRouter(prefix="/settings", tags=["settings"])

class SettingsUpdate(BaseModel):
    rapid_switching_high_threshold: int = Field(default=4, ge=1, le=50)
    rapid_switching_critical_threshold: int = Field(default=8, ge=1, le=100)
    rapid_switching_window_seconds: int = Field(default=60, ge=10, le=600)
    excessive_idle_threshold_minutes: int = Field(default=45, ge=5, le=240)
    distraction_threshold_minutes: int = Field(default=5, ge=1, le=120)
    after_hours_min_active_minutes: int = Field(default=5, ge=1, le=60)

@router.get("", response_model=SettingsUpdate)
async def get_settings(
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemSettings))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return SettingsUpdate(
        rapid_switching_high_threshold=settings.rapid_switching_high_threshold,
        rapid_switching_critical_threshold=settings.rapid_switching_critical_threshold,
        rapid_switching_window_seconds=settings.rapid_switching_window_seconds,
        excessive_idle_threshold_minutes=settings.excessive_idle_threshold_minutes,
        distraction_threshold_minutes=settings.distraction_threshold_minutes,
        after_hours_min_active_minutes=settings.after_hours_min_active_minutes,
    )

@router.put("", response_model=SettingsUpdate)
async def update_settings(
    payload: SettingsUpdate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemSettings))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = SystemSettings()
        db.add(settings)

    settings.rapid_switching_high_threshold = payload.rapid_switching_high_threshold
    settings.rapid_switching_critical_threshold = payload.rapid_switching_critical_threshold
    settings.rapid_switching_window_seconds = payload.rapid_switching_window_seconds
    settings.excessive_idle_threshold_minutes = payload.excessive_idle_threshold_minutes
    settings.distraction_threshold_minutes = payload.distraction_threshold_minutes
    settings.after_hours_min_active_minutes = payload.after_hours_min_active_minutes

    await db.commit()
    await db.refresh(settings)

    return SettingsUpdate(
        rapid_switching_high_threshold=settings.rapid_switching_high_threshold,
        rapid_switching_critical_threshold=settings.rapid_switching_critical_threshold,
        rapid_switching_window_seconds=settings.rapid_switching_window_seconds,
        excessive_idle_threshold_minutes=settings.excessive_idle_threshold_minutes,
        distraction_threshold_minutes=settings.distraction_threshold_minutes,
        after_hours_min_active_minutes=settings.after_hours_min_active_minutes,
    )
