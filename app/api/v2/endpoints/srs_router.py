"""Standalone SRS endpoints (outside of the /learning namespace)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user, get_db
from app.models.user.user_model import User
from app.api.v2.endpoints.learning_router import _build_empty_srs_summary

router = APIRouter()


@router.get("/summary", summary="Résumé global de répétition espacée")
def get_root_srs_summary(
    db: Session = Depends(get_db),  # noqa: ARG001 - Placeholder for future queries
    current_user: User = Depends(get_current_user),
) -> dict:
    """Expose the same empty payload as the learning namespace."""

    return _build_empty_srs_summary(current_user)
