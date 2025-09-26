"""Learning-related API endpoints.

These routes currently expose placeholder data so that the
frontend can safely call the spaced-repetition (SRS) and
learning journal features without receiving 404 errors.
Once the dedicated services are implemented the handlers can
be extended to return real analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user, get_db
from app.models.user.user_model import User

router = APIRouter()


def _build_empty_journal_response(limit: int) -> dict:
    """Return a consistent empty payload for journal endpoints."""

    return {
        "entries": [],
        "pagination": {
            "limit": limit,
            "returned": 0,
            "has_more": False,
        },
    }


def _build_empty_srs_summary(user: User) -> dict:
    """Return a placeholder SRS summary for the authenticated user."""

    return {
        "user_id": user.id,
        "due_today": 0,
        "overdue": 0,
        "new_available": 0,
        "streak": 0,
        "last_reviewed_at": None,
    }


@router.get("/srs/summary", summary="Résumé de répétition espacée")
def get_srs_summary(
    db: Session = Depends(get_db),  # noqa: ARG001 - Reserved for future use
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a default spaced-repetition summary for the user."""

    return _build_empty_srs_summary(current_user)


@router.get("/journal/entries", summary="Entrées du journal d'apprentissage")
def list_learning_journal_entries(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - Reserved for future use
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - Authentication guard
) -> dict:
    """Return an empty list of learning journal entries for now."""

    return _build_empty_journal_response(limit)
