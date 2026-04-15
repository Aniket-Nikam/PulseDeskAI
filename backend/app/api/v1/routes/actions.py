"""
PulseDesk Action Items Routes — Production
Manages coaching action items and task completion tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_serializer, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.db.session import get_db
from app.models import ActionItem, Employee
from app.api.v1.routes.auth import require_admin_read, require_admin_write
from app.core.logging import get_logger
from app.core.audit import log_admin_action

router = APIRouter(prefix="/actions", tags=["actions"])
log = get_logger("actions")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ActionItemCreate(BaseModel):
    employee_id: uuid.UUID  # Fixed: was str, now properly typed
    action_text: str = Field(min_length=3, max_length=500)
    priority: str = Field(default="medium", min_length=3, max_length=20)
    due_date: Optional[str] = None
    report_id: Optional[str] = Field(default=None, max_length=100)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"low", "medium", "high"}:
            raise ValueError("priority must be one of: low, medium, high")
        return normalized


class ActionItemUpdate(BaseModel):
    is_completed: Optional[bool] = None
    action_text: Optional[str] = Field(default=None, min_length=3, max_length=500)
    priority: Optional[str] = None
    due_date: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"low", "medium", "high"}:
            raise ValueError("priority must be one of: low, medium, high")
        return normalized


class ActionItemResponse(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    action_text: str
    is_completed: bool
    priority: str
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('id', 'employee_id')
    def serialize_uuid(self, value):
        return str(value) if value else None

    @field_serializer('created_at', 'updated_at', 'due_date', 'completed_at')
    def serialize_datetime(self, value):
        return value.isoformat() if value else None

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ActionItemResponse)
async def create_action_item(
    data: ActionItemCreate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Create a new action item for an employee"""
    # Verify employee exists
    emp_result = await db.execute(
        select(Employee).where(Employee.id == data.employee_id)
    )
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Employee not found")

    due_date = None
    if data.due_date:
        try:
            due_date = datetime.fromisoformat(data.due_date.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid due_date format: {e}")

    item = ActionItem(
        employee_id=data.employee_id,
        action_text=data.action_text,
        priority=data.priority,
        due_date=due_date,
        report_id=data.report_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    log.info("action_item_created", item_id=str(item.id), employee_id=str(data.employee_id))
    log_admin_action(
        "action_item_created",
        admin_id=str(admin.id),
        action_item_id=str(item.id),
        employee_id=str(data.employee_id),
    )
    return item


@router.get("/{item_id}", response_model=ActionItemResponse)
async def get_action_item(
    item_id: uuid.UUID,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific action item"""
    result = await db.execute(
        select(ActionItem).where(ActionItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
    return item


@router.get("/employee/{employee_id}", response_model=List[ActionItemResponse])
async def get_employee_action_items(
    employee_id: uuid.UUID,
    completed: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Get action items for an employee"""
    query = select(ActionItem).where(
        ActionItem.employee_id == employee_id
    )

    if completed is not None:
        query = query.where(ActionItem.is_completed == completed)

    query = query.order_by(ActionItem.created_at.desc()).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()
    return items


@router.patch("/{item_id}", response_model=ActionItemResponse)
async def update_action_item(
    item_id: uuid.UUID,
    data: ActionItemUpdate,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Update an action item (toggle completion, edit text, etc.)"""
    result = await db.execute(
        select(ActionItem).where(ActionItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    # Update fields if provided
    if data.is_completed is not None:
        item.is_completed = data.is_completed
        if data.is_completed:
            item.completed_at = datetime.now(timezone.utc)
        else:
            item.completed_at = None

    if data.action_text is not None:
        item.action_text = data.action_text

    if data.priority is not None:
        item.priority = data.priority

    if data.due_date is not None:
        try:
            item.due_date = datetime.fromisoformat(data.due_date.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid due_date format: {e}")

    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)

    log.info("action_item_updated", item_id=str(item_id))
    log_admin_action("action_item_updated", admin_id=str(admin.id), action_item_id=str(item.id))
    return item


@router.delete("/{item_id}")
async def delete_action_item(
    item_id: uuid.UUID,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    """Delete an action item"""
    result = await db.execute(
        select(ActionItem).where(ActionItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    await db.delete(item)
    await db.commit()

    log.info("action_item_deleted", item_id=str(item_id))
    log_admin_action("action_item_deleted", admin_id=str(admin.id), action_item_id=str(item_id))
    return {"deleted": True}


@router.get("/employee/{employee_id}/completion-stats")
async def get_completion_stats(
    employee_id: uuid.UUID,
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Get action item completion statistics for an employee"""
    # Total and completed counts
    total_result = await db.execute(
        select(func.count(ActionItem.id)).where(
            ActionItem.employee_id == employee_id
        )
    )
    total = total_result.scalar() or 0

    completed_result = await db.execute(
        select(func.count(ActionItem.id)).where(
            and_(
                ActionItem.employee_id == employee_id,
                ActionItem.is_completed == True
            )
        )
    )
    completed = completed_result.scalar() or 0

    completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

    return {
        "employee_id": str(employee_id),
        "total_items": total,
        "completed_items": completed,
        "completion_rate": completion_rate,
    }
