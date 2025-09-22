"""In-memory manager responsible for conversation websocket state."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Deque, List, MutableMapping, MutableSet

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocketState

from .schemas import ChannelDescriptor, ConversationMessage

log = logging.getLogger("conversation_ws")


class ConversationWebSocketManager:
    """Manage websocket connections and message history for conversations."""

    def __init__(self, history_size: int = 200) -> None:
        self._history_size = history_size
        self._connections: MutableMapping[str, MutableSet[WebSocket]] = {}
        self._messages: MutableMapping[str, Deque[ConversationMessage]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, channel: ChannelDescriptor, websocket: WebSocket) -> None:
        """Accept and register a websocket for the given channel."""

        await websocket.accept()
        key = channel.key
        async with self._lock:
            self._connections.setdefault(key, set()).add(websocket)
        log.info("[WS CONVERSATION CONNECT] channel=%s total=%s", key, await self.connection_count(channel))

    async def disconnect(self, channel: ChannelDescriptor, websocket: WebSocket) -> None:
        """Remove a websocket from the given channel."""

        key = channel.key
        async with self._lock:
            connections = self._connections.get(key)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(key, None)
        log.info("[WS CONVERSATION DISCONNECT] channel=%s remaining=%s", key, await self.connection_count(channel))

    async def connection_count(self, channel: ChannelDescriptor) -> int:
        """Return the number of active websocket connections for a channel."""

        key = channel.key
        async with self._lock:
            return len(self._connections.get(key, set()))

    async def broadcast_message(self, channel: ChannelDescriptor, message: ConversationMessage) -> None:
        """Store the message in history and broadcast it to every subscriber."""

        await self._store_message(channel, message)
        payload = {"type": "message", "payload": message.model_dump(mode="json")}
        await self._broadcast(channel, payload)

    async def send_history(self, channel: ChannelDescriptor, websocket: WebSocket) -> None:
        """Send the cached history to a single websocket connection."""

        history = await self.history(channel)
        payload = {
            "type": "history",
            "payload": [message.model_dump(mode="json") for message in history],
        }
        await self._send_payload(websocket, payload)

    async def history(self, channel: ChannelDescriptor) -> List[ConversationMessage]:
        """Return a copy of the cached history for a channel."""

        key = channel.key
        async with self._lock:
            buffer = self._messages.get(key, deque(maxlen=self._history_size))
            return list(buffer)

    async def _store_message(self, channel: ChannelDescriptor, message: ConversationMessage) -> None:
        key = channel.key
        async with self._lock:
            buffer = self._messages.get(key)
            if buffer is None:
                buffer = deque(maxlen=self._history_size)
                self._messages[key] = buffer
            buffer.append(message)

    async def _broadcast(self, channel: ChannelDescriptor, payload: dict) -> None:
        key = channel.key
        websockets = await self._connections_snapshot(key)
        if not websockets:
            return
        text_payload = self._encode_payload(payload)
        stale: list[WebSocket] = []
        for websocket in websockets:
            try:
                if websocket.application_state != WebSocketState.CONNECTED:
                    stale.append(websocket)
                    continue
                await websocket.send_text(text_payload)
            except Exception:  # pragma: no cover - defensive
                log.exception("[WS CONVERSATION SEND ERROR] channel=%s", key)
                stale.append(websocket)
        if stale:
            async with self._lock:
                connections = self._connections.get(key)
                if connections:
                    for websocket in stale:
                        connections.discard(websocket)
                    if not connections:
                        self._connections.pop(key, None)

    async def _connections_snapshot(self, key: str) -> List[WebSocket]:
        async with self._lock:
            return list(self._connections.get(key, set()))

    async def _send_payload(self, websocket: WebSocket, payload: dict) -> None:
        text_payload = self._encode_payload(payload)
        try:
            await websocket.send_text(text_payload)
        except Exception:  # pragma: no cover - defensive
            log.exception("[WS CONVERSATION SEND ERROR] single websocket")

    def _encode_payload(self, payload: dict) -> str:
        return json.dumps(jsonable_encoder(payload), ensure_ascii=False, separators=(",", ":"))


conversation_ws_manager = ConversationWebSocketManager()
