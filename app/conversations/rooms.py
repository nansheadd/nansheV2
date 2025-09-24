"""Utilities to expose available chat rooms for the conversation service."""

from __future__ import annotations

from typing import Iterable, List, Set

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conversations.schemas import ChannelDescriptor, ConversationScope
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.utility_models import UserCapsuleEnrollment
from app.models.user.user_model import User


class ChatRoom(BaseModel):
    """Representation of a conversation room returned by the REST API."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    key: str
    scope: ConversationScope
    domain: str | None = None
    area: str | None = None
    title: str
    description: str | None = None


def build_rooms_for_user(db: Session, user: User) -> List[ChatRoom]:
    """Return the list of chat rooms available to ``user``.

    The general room is always available. Additional rooms are derived from the
    capsules the user is enrolled in. Each unique ``(domain, area)`` pair yields
    a dedicated conversation room.
    """

    rooms: list[ChatRoom] = []
    seen_keys: Set[str] = set()

    general_descriptor = ChannelDescriptor.from_params()
    rooms.append(_descriptor_to_room(general_descriptor))
    seen_keys.add(general_descriptor.key)

    for descriptor in _iter_enrollment_descriptors(db, user.id):
        if descriptor.key in seen_keys:
            continue
        rooms.append(_descriptor_to_room(descriptor))
        seen_keys.add(descriptor.key)

    return rooms


def _descriptor_to_room(descriptor: ChannelDescriptor) -> ChatRoom:
    title = _format_descriptor_title(descriptor)
    description = None
    if descriptor.scope == ConversationScope.GENERAL:
        description = "Discussion globale de la communauté"

    return ChatRoom(
        key=descriptor.key,
        scope=descriptor.scope,
        domain=descriptor.domain,
        area=descriptor.area,
        title=title,
        description=description,
    )


def _format_descriptor_title(descriptor: ChannelDescriptor) -> str:
    if descriptor.scope == ConversationScope.GENERAL:
        return "Salon général"

    parts = [descriptor.domain or ""]
    if descriptor.area:
        parts.append(descriptor.area)

    title = " · ".join(part for part in parts if part)
    return title or descriptor.key


def _iter_enrollment_descriptors(db: Session, user_id: int) -> Iterable[ChannelDescriptor]:
    """Yield channel descriptors based on the user's capsule enrollments."""

    stmt = (
        select(Capsule.domain, Capsule.area)
        .join(UserCapsuleEnrollment, Capsule.id == UserCapsuleEnrollment.capsule_id)
        .where(UserCapsuleEnrollment.user_id == user_id)
        .distinct()
        .order_by(Capsule.domain.asc(), Capsule.area.asc())
    )

    result = db.execute(stmt)
    for domain, area in result:
        yield ChannelDescriptor.from_params(domain=domain, area=area)
