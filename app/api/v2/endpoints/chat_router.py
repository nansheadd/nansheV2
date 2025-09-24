"""REST endpoints for the conversation/chat service."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user, get_db
from app.conversations.rooms import ChatRoom, build_rooms_for_user
from app.models.user.user_model import User


router = APIRouter()


@router.get("/rooms", response_model=list[ChatRoom])
def list_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatRoom]:
    """Return the chat rooms available to the authenticated user."""

    return build_rooms_for_user(db, current_user)
