# app/notifications/websocket_manager.py
import asyncio
import logging
import json
from typing import Dict, Set
from enum import Enum
from uuid import UUID
from decimal import Decimal
from datetime import datetime

import anyio
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocketState

log = logging.getLogger("ws")

class NotificationWebSocketManager:
    def __init__(self) -> None:
        self.connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(user_id, set()).add(websocket)
        log.info(f"[WS CONNECT] user={user_id} total_sockets_for_user={len(self.connections[user_id])}")

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        conns = self.connections.get(user_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self.connections.pop(user_id, None)
        log.info(f"[WS DISCONNECT] user={user_id} remaining={len(self.connections.get(user_id, []))}")

    def _json_safe(self, payload: dict) -> str:
        # Encodage robuste : Enums -> .value, datetime -> isoformat, UUID -> str, Decimal -> float
        enc = jsonable_encoder(
            payload,
            custom_encoder={
                Enum: lambda e: getattr(e, "value", str(e)),
                datetime: lambda d: d.isoformat(),
                UUID: str,
                Decimal: float,
            },
        )
        # dumps ici évite les erreurs dans ws.send_json
        return json.dumps(enc, ensure_ascii=False, separators=(",", ":"))

    async def _send(self, user_id: int, payload: dict) -> None:
        websockets = list(self.connections.get(user_id, []))
        log.info(f"[WS SEND] user={user_id} sockets={len(websockets)} type={payload.get('type')}")
        if not websockets:
            return

        # ⚠️ sérialise AVANT la boucle pour éviter de drop la socket sur erreur
        try:
            text = self._json_safe(payload)
        except Exception as e:
            log.exception(f"[WS ENCODE ERROR] user={user_id}: {e} payload={payload!r}")
            return

        dead = []
        for ws in websockets:
            try:
                if ws.application_state != WebSocketState.CONNECTED:
                    dead.append(ws)
                    continue
                # on envoie du texte déjà sérialisé
                await ws.send_text(text)
            except Exception as e:
                log.exception(f"[WS SEND ERROR] user={user_id}: {e}")
                dead.append(ws)

        for ws in dead:
            self.disconnect(user_id, ws)

    async def notify_async(self, user_id: int, payload: dict) -> None:
        await self._send(user_id, payload)

    def notify(self, user_id: int, payload: dict) -> None:
        try:
            anyio.from_thread.run(self._send, user_id, payload)
            return
        except RuntimeError:
            pass
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send(user_id, payload))
            return
        except RuntimeError:
            asyncio.run(self._send(user_id, payload))


notification_ws_manager = NotificationWebSocketManager()
