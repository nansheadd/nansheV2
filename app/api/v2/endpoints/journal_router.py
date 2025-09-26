"""Journal endpoints returning placeholder data.

The frontend expects these routes to exist even though the
persistence layer is not yet implemented.
"""

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user, get_db
from app.models.user.user_model import User
from app.api.v2.endpoints.learning_router import _build_error_journal_demo
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class JournalRequest(BaseModel):
    """Payload accepted by journal endpoints."""

    model_config = ConfigDict(extra="allow")

    limit: int | None = Field(default=None, ge=1, le=50)


def _resolve_limit(limit: int | None, payload: JournalRequest | None) -> int:
    if payload and payload.limit is not None:
        return payload.limit
    if limit is not None:
        return limit
    return 10


@router.get("/", summary="Résumé du journal")
def list_journal_entries(
    limit: int | None = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for later use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """Return the same demo payload as the learning journal endpoint."""

    return _build_error_journal_demo(_resolve_limit(limit, None))


@router.post("/", summary="Résumé du journal")
def post_journal_entries(
    payload: JournalRequest | None = Body(default=None),
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for later use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """POST alias returning the same payload as :func:`list_journal_entries`."""

    return _build_error_journal_demo(_resolve_limit(None, payload))


@router.get("/entries", summary="Entrées détaillées du journal")
def list_journal_entries_explicit(
    limit: int | None = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for later use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """Alias of :func:`list_journal_entries` for frontend compatibility."""

    return _build_error_journal_demo(_resolve_limit(limit, None))


@router.post("/entries", summary="Entrées détaillées du journal")
def post_journal_entries_explicit(
    payload: JournalRequest | None = Body(default=None),
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for later use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """POST alias mirroring :func:`list_journal_entries_explicit`."""

    return _build_error_journal_demo(_resolve_limit(None, payload))
