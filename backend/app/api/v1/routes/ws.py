"""
WebSocket endpoint for real-time dashboard updates.
Admins connect and receive live employee activity pushes.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.services.ws_broadcaster import manager
from app.core.security import decode_token
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models import Admin, UserRole
from jose import JWTError

router = APIRouter(tags=["websocket"])
log = get_logger("websocket")


def _allowed_ws_origins() -> set[str]:
    return {origin.rstrip("/") for origin in settings.cors_origins_list}


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket, token: str | None = Query(default=None)):
    """
    Connect with either:
      - HttpOnly access cookie (preferred)
      - ?token=<access_token> (legacy fallback)
    Receives JSON pushes: { "type": "employee_update", "data": {...} }
    """
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin and origin not in _allowed_ws_origins():
        await websocket.close(code=4003)
        return

    if not token:
        token = websocket.cookies.get(settings.ACCESS_COOKIE_NAME)
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
        admin_id = payload.get("sub")
        if not admin_id:
            await websocket.close(code=4001)
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Admin).where(Admin.id == admin_id, Admin.is_active))
            admin = result.scalar_one_or_none()
            if not admin or admin.role not in {UserRole.super_admin, UserRole.admin, UserRole.manager}:
                await websocket.close(code=4003)
                return
    except JWTError:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket)
    admin_id = payload.get("sub", "unknown")
    log.info("ws_admin_connected", admin_id=admin_id)

    try:
        while True:
            # Keep alive: client sends pings, we just need the loop alive
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("ws_admin_disconnected", admin_id=admin_id)
