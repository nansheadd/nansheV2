"""CRUD helpers for coach tutorial progress."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.toolbox.coach_tutorial_model import CoachTutorialState
from app.schemas.toolbox import TutorialStatus
from app.models.user.user_model import User


def list_states_for_user(db: Session, user: User) -> list[CoachTutorialState]:
    return (
        db.query(CoachTutorialState)
        .filter(CoachTutorialState.user_id == user.id)
        .order_by(CoachTutorialState.tutorial_key.asc())
        .all()
    )


def get_state(db: Session, user: User, tutorial_key: str) -> CoachTutorialState | None:
    return (
        db.query(CoachTutorialState)
        .filter(
            CoachTutorialState.user_id == user.id,
            CoachTutorialState.tutorial_key == tutorial_key,
        )
        .first()
    )


def upsert_state(
    db: Session,
    user: User,
    *,
    tutorial_key: str,
    status: TutorialStatus | None = None,
    last_step_index: int | None = None,
) -> CoachTutorialState:
    state = get_state(db, user, tutorial_key)
    if state is None:
        state = CoachTutorialState(user_id=user.id, tutorial_key=tutorial_key)
        db.add(state)

    if status is not None:
        normalized = status.value if isinstance(status, TutorialStatus) else str(status).lower()
        state.status = normalized
        if state.status == TutorialStatus.IN_PROGRESS.value:
            state.mark_started()
        if state.status == TutorialStatus.COMPLETED.value:
            state.mark_completed()

    if last_step_index is not None:
        state.last_step_index = last_step_index

    state.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(state)
    return state
