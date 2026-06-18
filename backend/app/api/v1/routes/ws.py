"""
WebSocket endpoint for real-time dashboard updates.
Admins connect and receive live employee activity pushes.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.services.ws_broadcaster import manager, stream_manager
from app.core.security import decode_token, device_token_lookup_values, is_private_or_local_origin, check_admin_can_view_employee
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models import Admin, UserRole, Device, DeviceStatus
from jose import JWTError
import uuid

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
    await websocket.accept()
    
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin and origin not in _allowed_ws_origins() and not is_private_or_local_origin(origin):
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
        pass
    except Exception as e:
        log.warning("ws_admin_error", admin_id=admin_id, error=str(e))
    finally:
        manager.disconnect(websocket)
        log.info("ws_admin_disconnected", admin_id=admin_id)


@router.websocket("/ws/screen-stream")
async def screen_stream(websocket: WebSocket, device_token: str | None = Query(default=None)):
    """
    Agent connects here to stream screen frames.
    Requires X-Device-Token header. Query token is accepted only for older agents.
    """
    await websocket.accept()
    log.info("ws_agent_stream_accepted", client=str(websocket.client))
    if not device_token:
        device_token = websocket.headers.get("x-device-token")
    if not device_token:
        log.warning("ws_agent_stream_rejected: no device token provided")
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device).where(Device.device_token.in_(device_token_lookup_values(device_token)))
        )
        device = result.scalar_one_or_none()
        if not device or device.status != DeviceStatus.approved:
            log.warning("ws_agent_stream_rejected: device not found or not approved",
                       device_found=device is not None,
                       status=str(device.status) if device else "N/A")
            await websocket.close(code=4003)
            return
        if not device.monitoring_consent_given:
            log.warning("ws_agent_stream_rejected: monitoring consent not given",
                       employee_id=str(device.employee_id), device_id=str(device.id))
            await websocket.close(code=4003)
            return
        employee_id = str(device.employee_id)

    await stream_manager.register_agent(employee_id, websocket)
    log.info("ws_agent_stream_connected", employee_id=employee_id, device_id=str(device.id))

    try:
        while True:
            raw = await websocket.receive()
            # Handle both text and binary frames, plus disconnects
            if raw.get("type") == "websocket.disconnect":
                break
            text = raw.get("text")
            if text is None:
                # Binary frame or other non-text — skip
                continue
            try:
                data = __import__("json").loads(text)
            except Exception:
                # Non-JSON text (e.g. "ping") — ignore
                continue
            if data.get("type") == "screen_frame":
                await stream_manager.relay_frame(employee_id, data)
    except WebSocketDisconnect:
        log.info("ws_agent_stream_disconnected", employee_id=employee_id)
    except Exception as e:
        log.warning("ws_agent_stream_error", employee_id=employee_id, error=str(e), error_type=type(e).__name__)
    finally:
        stream_manager.unregister_agent(employee_id)


@router.websocket("/ws/screen-view/{employee_id}")
async def screen_view(
    websocket: WebSocket,
    employee_id: str,
    token: str | None = Query(default=None)
):
    """
    Admins connect here to view real-time screen stream for an employee.
    Requires admin authentication.
    """
    await websocket.accept()
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin and origin not in _allowed_ws_origins() and not is_private_or_local_origin(origin):
        log.warning("ws_admin_viewer_rejected: origin not allowed", origin=origin)
        await websocket.close(code=4003)
        return

    if not token:
        token = websocket.cookies.get(settings.ACCESS_COOKIE_NAME)
    if not token:
        log.warning("ws_admin_viewer_rejected: no auth token")
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            log.warning("ws_admin_viewer_rejected: invalid token type")
            await websocket.close(code=4001)
            return
        admin_id = payload.get("sub")
        if not admin_id:
            log.warning("ws_admin_viewer_rejected: no admin id in token")
            await websocket.close(code=4001)
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Admin).where(Admin.id == admin_id, Admin.is_active))
            admin = result.scalar_one_or_none()
            if not admin or admin.role not in {UserRole.super_admin, UserRole.admin, UserRole.manager}:
                log.warning("ws_admin_viewer_rejected: insufficient role", admin_id=admin_id)
                await websocket.close(code=4003)
                return
            
            # ✅ PRIVACY CHECK: Verify admin can access this employee's screen stream
            # Must be inside db session context!
            can_access = await check_admin_can_view_employee(
                admin_id=admin.id,
                admin_role=admin.role.value,
                employee_id=uuid.UUID(employee_id),
                db=db,
            )
            
            if not can_access:
                log.warning(
                    "unauthorized_screen_stream_access",
                    admin_id=str(admin.id),
                    admin_role=admin.role.value,
                    employee_id=employee_id,
                )
                await websocket.close(code=4003, reason="Access denied to this employee's stream")
                return
    except JWTError:
        log.warning("ws_admin_viewer_rejected: JWT decode error")
        await websocket.close(code=4001)
        return
    
    await stream_manager.register_admin(employee_id, websocket)
    admin_id = payload.get("sub", "unknown")
    log.info("ws_admin_viewer_connected", employee_id=employee_id, admin_id=admin_id)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("ws_admin_viewer_error", employee_id=employee_id, error=str(e))
    finally:
        await stream_manager.unregister_admin(employee_id, websocket)
        log.info("ws_admin_viewer_disconnected", employee_id=employee_id, admin_id=admin_id)
