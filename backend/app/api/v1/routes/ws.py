"""
WebSocket endpoint for real-time dashboard updates.
Admins connect and receive live employee activity pushes.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.ws_broadcaster import manager
from app.core.security import decode_token
from app.core.logging import get_logger
from jose import JWTError

router = APIRouter(tags=["websocket"])
log = get_logger("websocket")


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket, token: str = Query(...)):
    """
    Connect with ?token=<access_token>
    Receives JSON pushes: { "type": "employee_update", "data": {...} }
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
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
