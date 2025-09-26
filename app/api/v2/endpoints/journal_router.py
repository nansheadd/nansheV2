"""Journal endpoints returning placeholder data.

The frontend expects these routes to exist even though the
persistence layer is not yet implemented.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user, get_db
from app.models.user.user_model import User
from app.api.v2.endpoints.learning_router import _build_empty_journal_response

router = APIRouter()


@router.get("/", summary="Résumé du journal")
def list_journal_entries(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for later use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """Return an empty set of journal entries with pagination metadata."""

    return _build_empty_journal_response(limit)


@router.get("/entries", summary="Entrées détaillées du journal")
def list_journal_entries_explicit(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for later use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """Alias of :func:`list_journal_entries` for frontend compatibility."""

    return _build_empty_journal_response(limit)
