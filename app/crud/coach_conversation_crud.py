"""Persistence helpers for coach IA conversations grouped by location."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.toolbox.coach_conversation_model import (
    CoachConversationLocation,
    CoachConversationMessage,
    CoachConversationRole,
    CoachConversationThread,
)
from app.models.user.user_model import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def determine_location(
    *,
    capsule: Capsule | None,
    molecule: Molecule | None,
) -> tuple[CoachConversationLocation, int | None, int | None]:
    """Return the location enum and associated identifiers for the conversation."""

    if molecule is not None:
        capsule_from_molecule = getattr(getattr(molecule, "granule", None), "capsule", None)
        capsule_id = getattr(capsule_from_molecule, "id", None)
        return CoachConversationLocation.MOLECULE, capsule_id, molecule.id

    if capsule is not None:
        return CoachConversationLocation.CAPSULE, capsule.id, None

    return CoachConversationLocation.DASHBOARD, None, None


def get_or_create_thread(
    db: Session,
    user: User,
    *,
    location: CoachConversationLocation,
    capsule_id: int | None,
    molecule_id: int | None,
) -> CoachConversationThread:
    """Return an existing thread for the given location or create it."""

    location_key = CoachConversationThread.build_location_key(
        location=location, capsule_id=capsule_id, molecule_id=molecule_id
    )

    thread = (
        db.query(CoachConversationThread)
        .filter(
            CoachConversationThread.user_id == user.id,
            CoachConversationThread.location_key == location_key,
        )
        .first()
    )
    if thread:
        return thread

    thread = CoachConversationThread(
        user_id=user.id,
        location=location,
        location_key=location_key,
        capsule_id=capsule_id,
        molecule_id=molecule_id,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def append_message(
    db: Session,
    thread: CoachConversationThread,
    *,
    role: CoachConversationRole,
    content: str,
    payload: dict | None = None,
) -> CoachConversationMessage:
    """Persist a new message and update the thread timestamp."""

    message = CoachConversationMessage(
        thread_id=thread.id,
        role=role,
        content=content,
        payload=payload,
    )
    thread.updated_at = _now()

    db.add_all([thread, message])
    db.commit()
    db.refresh(message)
    return message


def append_user_message(
    db: Session,
    thread: CoachConversationThread,
    *,
    content: str,
    payload: dict | None = None,
) -> CoachConversationMessage:
    return append_message(db, thread, role=CoachConversationRole.USER, content=content, payload=payload)


def append_coach_message(
    db: Session,
    thread: CoachConversationThread,
    *,
    content: str,
    payload: dict | None = None,
) -> CoachConversationMessage:
    return append_message(db, thread, role=CoachConversationRole.COACH, content=content, payload=payload)


def list_threads_for_user(db: Session, user: User) -> list[CoachConversationThread]:
    """Return every conversation thread available to ``user`` sorted by recency."""

    return (
        db.query(CoachConversationThread)
        .options(
            joinedload(CoachConversationThread.capsule),
            joinedload(CoachConversationThread.molecule).joinedload(Molecule.granule).joinedload(Granule.capsule),
        )
        .filter(CoachConversationThread.user_id == user.id)
        .order_by(CoachConversationThread.updated_at.desc())
        .all()
    )


def get_thread_for_user(db: Session, user: User, thread_id: int) -> CoachConversationThread | None:
    return (
        db.query(CoachConversationThread)
        .options(
            joinedload(CoachConversationThread.capsule),
            joinedload(CoachConversationThread.molecule).joinedload(Molecule.granule).joinedload(Granule.capsule),
        )
        .filter(
            CoachConversationThread.id == thread_id,
            CoachConversationThread.user_id == user.id,
        )
        .first()
    )


def list_messages_for_thread(
    db: Session,
    thread: CoachConversationThread,
    *,
    limit: int | None = None,
) -> list[CoachConversationMessage]:
    """Return messages ordered from oldest to newest for a thread."""

    query = (
        db.query(CoachConversationMessage)
        .filter(CoachConversationMessage.thread_id == thread.id)
        .order_by(CoachConversationMessage.created_at.asc(), CoachConversationMessage.id.asc())
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def fetch_thread_statistics(
    db: Session, thread_ids: Iterable[int]
) -> dict[int, tuple[int, datetime | None]]:
    """Return (message_count, last_message_at) per thread id."""

    thread_ids = list(thread_ids)
    if not thread_ids:
        return {}

    rows = (
        db.query(
            CoachConversationMessage.thread_id,
            func.count(CoachConversationMessage.id),
            func.max(CoachConversationMessage.created_at),
        )
        .filter(CoachConversationMessage.thread_id.in_(thread_ids))
        .group_by(CoachConversationMessage.thread_id)
        .all()
    )

    stats: dict[int, tuple[int, datetime | None]] = {}
    for thread_id, message_count, last_message_at in rows:
        stats[int(thread_id)] = (int(message_count), last_message_at)
    return stats


def bulk_delete_threads(db: Session, threads: Iterable[CoachConversationThread]) -> int:
    """Delete multiple conversation threads. Returns the number of deleted threads."""

    count = 0
    for thread in threads:
        db.delete(thread)
        count += 1
    if count:
        db.commit()
    return count
