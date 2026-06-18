import json
from typing import List
from fastapi import WebSocket
from app.core.logging import get_logger

log = get_logger("ws_broadcaster")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        self.active_connections.append(websocket)
        log.debug("ws_connection_added", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.debug("ws_connection_removed", total=len(self.active_connections))

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


async def broadcast_employee_update(data: dict):
    await manager.broadcast({"type": "employee_update", "data": data})


async def broadcast_device_status(data: dict):
    await manager.broadcast({"type": "device_status", "data": data})


async def broadcast_anomaly(data: dict):
    await manager.broadcast({"type": "anomaly", "data": data})


async def broadcast_break_alert(data: dict):
    await manager.broadcast({"type": "break_alert", "data": data})


class ScreenStreamManager:
    MAX_VIEWERS_PER_EMPLOYEE = 5  # Cap concurrent admin viewers per stream
    MAX_SEND_BUFFER_BYTES = 100_000  # Skip frames if outgoing buffer exceeds 100KB

    def __init__(self):
        # employee_id -> agent WebSocket
        self.agent_connections: dict[str, WebSocket] = {}
        # employee_id -> list of admin WebSockets
        self.admin_connections: dict[str, list[WebSocket]] = {}
        # employee_id -> config dict {"enabled": bool, "fps": float, "quality": int}
        self.stream_configs: dict[str, dict] = {}

    def is_stream_enabled(self, employee_id: str) -> bool:
        # Stream is enabled only if there is an active admin viewer and it is not paused
        has_viewers = bool(self.admin_connections.get(employee_id))
        is_paused = self.stream_configs.get(employee_id, {}).get("enabled", True) is False
        return has_viewers and not is_paused

    def get_stream_config(self, employee_id: str) -> dict:
        enabled = self.is_stream_enabled(employee_id)
        config = self.stream_configs.get(employee_id, {})
        return {
            "enabled": enabled,
            "fps": config.get("fps", 24.0),
            "quality": config.get("quality", 50)
        }

    async def set_stream_config(self, employee_id: str, enabled: bool, fps: float = 24.0, quality: int = 50):
        # Update in-memory config
        self.stream_configs[employee_id] = {
            "enabled": enabled,
            "fps": fps,
            "quality": quality,
        }
        # Notify the agent (screen-stream) about new config so it can adjust its behavior
        agent_ws = self.agent_connections.get(employee_id)
        if agent_ws:
            try:
                await agent_ws.send_json({
                    "type": "config",
                    "enabled": enabled,
                    "fps": fps,
                    "quality": quality,
                })
            except Exception:
                pass
        # Broadcast the updated config to all connected admin viewers so UI reflects the change
        admins = self.admin_connections.get(employee_id, [])
        if admins:
            dead_admins = []
            payload = {"type": "config", "enabled": enabled, "fps": fps, "quality": quality}
            for admin_ws in admins:
                try:
                    await admin_ws.send_json(payload)
                except Exception:
                    dead_admins.append(admin_ws)
            for dead in dead_admins:
                await self.unregister_admin(employee_id, dead)

    async def register_agent(self, employee_id: str, websocket: WebSocket):
        self.agent_connections[employee_id] = websocket
        log.info("Agent registered", employee_id=employee_id)
        # Send current stream config (only enabled if an admin is already watching)
        config = self.get_stream_config(employee_id)
        try:
            await websocket.send_json({
                "type": "config",
                **config
            })
            log.info("agent_stream_registered", employee_id=employee_id, fps=config["fps"], enabled=config["enabled"])
        except Exception:
            pass

    def unregister_agent(self, employee_id: str):
        if employee_id in self.agent_connections:
            del self.agent_connections[employee_id]
            log.info("Agent unregistered", employee_id=employee_id)

    async def register_admin(self, employee_id: str, websocket: WebSocket):
        if employee_id not in self.admin_connections:
            self.admin_connections[employee_id] = []

        # Enforce connection limit per employee
        if len(self.admin_connections[employee_id]) >= self.MAX_VIEWERS_PER_EMPLOYEE:
            log.warning("max_viewers_reached", employee_id=employee_id, limit=self.MAX_VIEWERS_PER_EMPLOYEE)
            try:
                await websocket.close(code=1013, reason="Too many viewers for this stream")
            except Exception:
                pass
            return

        self.admin_connections[employee_id].append(websocket)
        log.info("Admin viewer registered", employee_id=employee_id, viewer_count=len(self.admin_connections[employee_id]))
        
        # Always tell the agent to stream when an admin is viewing
        config = self.get_stream_config(employee_id)
        config["enabled"] = True  # Force-enable since admin is watching
        agent_ws = self.agent_connections.get(employee_id)
        if agent_ws:
            try:
                await agent_ws.send_json({
                    "type": "config",
                    **config
                })
            except Exception:
                pass

    async def unregister_admin(self, employee_id: str, websocket: WebSocket):
        if employee_id in self.admin_connections:
            if websocket in self.admin_connections[employee_id]:
                self.admin_connections[employee_id].remove(websocket)
            if not self.admin_connections[employee_id]:
                del self.admin_connections[employee_id]
                log.info("Last admin viewer disconnected, disabling stream", employee_id=employee_id)
                config = self.get_stream_config(employee_id)
                agent_ws = self.agent_connections.get(employee_id)
                if agent_ws:
                    try:
                        await agent_ws.send_json({
                            "type": "config",
                            **config
                        })
                    except Exception:
                        pass

    async def relay_frame(self, employee_id: str, frame_payload: dict):
        # Only forward frames if streaming is enabled for this employee
        if not self.is_stream_enabled(employee_id):
            return
        admins = self.admin_connections.get(employee_id, [])
        if not admins:
            return
        # Pre-serialize once to avoid re-serializing per admin connection
        import json as _json
        try:
            payload_text = _json.dumps(frame_payload)
        except Exception:
            return
        dead_admins = []
        sent_count = 0
        dropped_count = 0
        for admin_ws in admins:
            try:
                # ✅ BUFFER CHECK: Skip frame if outgoing buffer is backed up (congestion)
                # This prevents memory bloat when a viewer is slow
                send_buffer_size = getattr(admin_ws, '_send_buffer_size', 0)
                if send_buffer_size > self.MAX_SEND_BUFFER_BYTES:
                    dropped_count += 1
                    continue
                
                await admin_ws.send_text(payload_text)
                sent_count += 1
            except Exception as e:
                # Log and mark for cleanup on send failure
                log.debug("frame_send_failed", employee_id=employee_id, error=str(e))
                dead_admins.append(admin_ws)
        
        # Cleanup dead connections
        for dead in dead_admins:
            await self.unregister_admin(employee_id, dead)
        
        if admins:
            log.debug("frame_relayed", employee_id=employee_id, sent=sent_count, dropped=dropped_count)


stream_manager = ScreenStreamManager()


