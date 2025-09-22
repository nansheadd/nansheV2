"""Tests for the in-memory conversation websocket manager."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from starlette.websockets import WebSocketState

from app.conversations.manager import ConversationWebSocketManager
from app.conversations.schemas import (
    ChannelDescriptor,
    ConversationMessage,
    MessageOptions,
    UserPublicInfo,
)


class DummyWebSocket:
    """Minimal websocket double capturing accepted and sent payloads."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[str] = []
        self.application_state = WebSocketState.CONNECTED

    async def accept(self) -> None:  # pragma: no cover - executed in tests
        self.accepted = True

    async def send_text(self, data: str) -> None:  # pragma: no cover - executed in tests
        self.sent.append(data)


@pytest.mark.asyncio
async def test_broadcast_and_history_are_kept_sorted() -> None:
    manager = ConversationWebSocketManager(history_size=2)
    channel = ChannelDescriptor.from_params()

    ws_a = DummyWebSocket()
    ws_b = DummyWebSocket()

    await manager.connect(channel, ws_a)
    await manager.connect(channel, ws_b)

    base_message = {
        "domain": channel.domain,
        "area": channel.area,
        "scope": channel.scope,
        "user": UserPublicInfo(id=1, username="tester"),
        "options": MessageOptions(),
    }

    message1 = ConversationMessage(
        id="msg-1",
        content="Premier message",
        created_at=datetime.now(timezone.utc),
        **base_message,
    )
    message2 = ConversationMessage(
        id="msg-2",
        content="Second message",
        created_at=datetime.now(timezone.utc),
        **base_message,
    )
    message3 = ConversationMessage(
        id="msg-3",
        content="Troisième message",
        created_at=datetime.now(timezone.utc),
        **base_message,
    )

    await manager.broadcast_message(channel, message1)
    await manager.broadcast_message(channel, message2)
    await manager.broadcast_message(channel, message3)

    assert ws_a.accepted and ws_b.accepted
    assert len(ws_a.sent) == 3

    last_payload = json.loads(ws_a.sent[-1])
    assert last_payload["type"] == "message"
    assert last_payload["payload"]["id"] == "msg-3"

    history = await manager.history(channel)
    assert [message.id for message in history] == ["msg-2", "msg-3"]

    ws_c = DummyWebSocket()
    await manager.connect(channel, ws_c)
    await manager.send_history(channel, ws_c)

    history_payload = json.loads(ws_c.sent[-1])
    assert history_payload["type"] == "history"
    assert [msg["id"] for msg in history_payload["payload"]] == ["msg-2", "msg-3"]


@pytest.mark.asyncio
async def test_disconnect_clears_connection() -> None:
    manager = ConversationWebSocketManager()
    channel = ChannelDescriptor.from_params(domain="Sciences", area="physique")

    websocket = DummyWebSocket()
    await manager.connect(channel, websocket)
    assert await manager.connection_count(channel) == 1

    await manager.disconnect(channel, websocket)
    assert await manager.connection_count(channel) == 0
