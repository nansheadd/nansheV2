"""WebSocket endpoint powering in-memory conversations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user_from_websocket, get_db
from app.conversations import (
    ChannelDescriptor,
    ConversationMessage,
    MessageOptions,
    UserPublicInfo,
    conversation_ws_manager,
)

router = APIRouter()
log = logging.getLogger("conversation_ws")


@router.websocket("/ws/conversations")
async def conversations_ws(
    websocket: WebSocket,
    domain: str | None = Query(default=None, description="Salon/domain for the conversation"),
    area: str | None = Query(default=None, description="Optional area tag for the conversation"),
    db: Session = Depends(get_db),
) -> None:
    """Authenticate the websocket, attach it to the right channel and stream messages."""

    try:
        current_user = get_current_user_from_websocket(websocket, db)
    except HTTPException as exc:
        if exc.detail == "token_expired":
            log.warning("Conversation WS refused: token expired")
        else:
            log.warning("Conversation WS refused: token invalid (%s)", exc.detail)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    channel = ChannelDescriptor.from_params(domain=domain, area=area)
    await conversation_ws_manager.connect(channel, websocket)
    log.info(
        "[WS CONVERSATION CONNECTED] user=%s channel=%s scope=%s",
        current_user.id,
        channel.key,
        channel.scope,
    )

    await websocket.send_json({"type": "channel.ready", "payload": channel.payload()})
    await conversation_ws_manager.send_history(channel, websocket)

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "invalid_json"})
                continue

            action = payload.get("action")
            if action == "send_message":
                await _handle_send_message(payload, websocket, channel, current_user)
            elif action == "request_history":
                await conversation_ws_manager.send_history(channel, websocket)
            elif action == "heartbeat":
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "payload": {"ts": datetime.now(timezone.utc).isoformat()},
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": "unknown_action",
                        "action": action,
                    }
                )
    except WebSocketDisconnect:
        log.info(
            "[WS CONVERSATION DISCONNECTED] user=%s channel=%s",
            current_user.id,
            channel.key,
        )
    finally:
        await conversation_ws_manager.disconnect(channel, websocket)


def _safe_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


async def _handle_send_message(payload: dict[str, Any], websocket: WebSocket, channel: ChannelDescriptor, user) -> None:
    content = _safe_text(payload.get("content"))
    if not content:
        await websocket.send_json({"type": "error", "error": "empty_message"})
        return

    options_data = payload.get("options") or {}
    try:
        options = MessageOptions(**options_data)
    except ValidationError as exc:
        await websocket.send_json(
            {
                "type": "error",
                "error": "invalid_options",
                "details": exc.errors(),
            }
        )
        return

    message = ConversationMessage(
        id=str(uuid4()),
        scope=channel.scope,
        domain=channel.domain,
        area=channel.area,
        content=content,
        created_at=datetime.now(timezone.utc),
        user=UserPublicInfo.model_validate(user),
        options=options,
    )
    await conversation_ws_manager.broadcast_message(channel, message)
