"""
Admin audit trail — writes to BOTH structlog AND the database.

Every call to log_admin_action() now persists a row in the admin_audit_logs
table so that admin activity is queryable from the dashboard.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

from app.core.logging import get_logger

audit_log = get_logger("audit")


def log_admin_action(
    action: str,
    *,
    admin_id: str,
    employee_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    **details: Any,
) -> None:
    """
    Log an admin action to both structlog (immediate) and the database (async).
    
    The DB write is fire-and-forget via asyncio.create_task when running inside
    an active event loop, or falls back to a background thread otherwise.
    """
    safe_details = {k: v for k, v in details.items() if v is not None}

    # 1. Always log to structlog (immediate, synchronous)
    audit_log.info(
        "admin_action",
        action=action,
        admin_id=admin_id,
        employee_id=employee_id,
        **safe_details,
    )

    # 2. Persist to database (fire-and-forget)
    _persist_to_db(
        action=action,
        admin_id=admin_id,
        employee_id=employee_id,
        ip_address=ip_address,
        details=safe_details,
    )


async def _db_insert(
    action: str,
    admin_id: str,
    employee_id: Optional[str],
    ip_address: Optional[str],
    details: dict,
) -> None:
    """Async coroutine that writes the audit entry using the app's existing session factory."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.models import AdminAuditLog

        async with AsyncSessionLocal() as db:
            entry = AdminAuditLog(
                admin_id=uuid.UUID(admin_id),
                action=action,
                target_employee_id=uuid.UUID(employee_id) if employee_id else None,
                metadata_json=details if details else None,
                ip_address=ip_address,
            )
            db.add(entry)
            await db.commit()
    except Exception as e:
        # Never let audit logging crash the main application
        audit_log.warning("audit_db_write_failed", error=str(e), action=action)


def _persist_to_db(
    *,
    action: str,
    admin_id: str,
    employee_id: Optional[str],
    ip_address: Optional[str],
    details: dict,
) -> None:
    """
    Schedule the DB write on the running event loop if available.
    This avoids the 'Future attached to a different loop' errors that occurred
    when we spawned background threads with their own event loops that tried to
    share asyncpg connections from the main pool.
    """
    coro = _db_insert(
        action=action,
        admin_id=admin_id,
        employee_id=employee_id,
        ip_address=ip_address,
        details=details,
    )

    try:
        loop = asyncio.get_running_loop()
        # We are inside the FastAPI async event loop — schedule as a task
        loop.create_task(coro)
    except RuntimeError:
        # No running loop (e.g. called from a sync CLI script) — skip DB write,
        # the structlog entry was already written above.
        audit_log.debug("audit_db_skipped_no_loop", action=action)
