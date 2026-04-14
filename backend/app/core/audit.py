from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

audit_log = get_logger("audit")


def log_admin_action(action: str, *, admin_id: str, **details: Any) -> None:
    safe_details = {k: v for k, v in details.items() if v is not None}
    audit_log.info("admin_action", action=action, admin_id=admin_id, **safe_details)
