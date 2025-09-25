"""Pydantic schemas exposing the coach IA conversation data."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.toolbox.coach_conversation_model import (
    CoachConversationLocation,
    CoachConversationRole,
    CoachConversationThread,
)


class CoachConversationMessageOut(BaseModel):
    """Serialized representation of a stored conversation message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    role: CoachConversationRole
    content: str
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime


class CoachConversationThreadOut(BaseModel):
    """Serialized conversation thread with contextual metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    location: CoachConversationLocation
    capsule_id: int | None = None
    capsule_title: str | None = Field(default=None)
    molecule_id: int | None = None
    molecule_title: str | None = Field(default=None)
    updated_at: datetime
    created_at: datetime
    last_message_at: datetime | None = None
    message_count: int = 0

    @classmethod
    def from_thread(
        cls,
        thread: CoachConversationThread,
        *,
        message_count: int,
        last_message_at: datetime | None,
    ) -> "CoachConversationThreadOut":
        return cls(
            id=thread.id,
            location=thread.location,
            capsule_id=thread.capsule_id,
            capsule_title=getattr(thread.capsule, "title", None),
            molecule_id=thread.molecule_id,
            molecule_title=getattr(thread.molecule, "title", None),
            updated_at=thread.updated_at,
            created_at=thread.created_at,
            last_message_at=last_message_at,
            message_count=message_count,
        )


class CoachConversationThreadList(BaseModel):
    """Response model containing multiple threads."""

    threads: List[CoachConversationThreadOut]


__all__ = [
    "CoachConversationMessageOut",
    "CoachConversationThreadOut",
    "CoachConversationThreadList",
]
