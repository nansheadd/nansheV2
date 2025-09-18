import asyncio
from typing import Dict, Set

import anyio
from fastapi import WebSocket


class NotificationWebSocketManager:
    def __init__(self) -> None:
        self.connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        conns = self.connections.get(user_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self.connections.pop(user_id, None)

    async def _send(self, user_id: int, payload: dict) -> None:
        websockets = list(self.connections.get(user_id, []))
        if not websockets:
            return

        dead: list[WebSocket] = []
        for ws in websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(user_id, ws)

    def notify(self, user_id: int, payload: dict) -> None:
        try:
            anyio.from_thread.run(self._send, user_id, payload)
        except RuntimeError:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.create_task(self._send(user_id, payload))


notification_ws_manager = NotificationWebSocketManager()
