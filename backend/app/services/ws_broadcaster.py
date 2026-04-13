import json
from typing import List
from fastapi import WebSocket
from app.core.logging import get_logger

log = get_logger("ws_broadcaster")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
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
