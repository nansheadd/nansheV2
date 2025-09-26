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


def _build_error_journal_demo(limit: int) -> dict:
    """Return a structured payload describing the smart error journal concept."""

    base_entries = [
        {
            "id": "smart-error-journal",
            "title": "Carnet d’erreurs intelligent",
            "headline": "Journal auto des fautes avec relance d’exercices similaires.",
            "description": (
                "Un journal qui agrège automatiquement les erreurs répétées, "
                "propose de refaire les exercices correspondants et suit la baisse des erreurs récurrentes."
            ),
            "value_proposition": [
                {
                    "label": "Journal automatique des fautes",
                    "details": (
                        "Chaque faute est historisée avec le concept touché et un raccourci « Refaire des exos similaires »."
                    ),
                },
                {
                    "label": "Cycles de révision intelligents",
                    "details": (
                        "Les atomes ratés et déjà générés sont recyclés tant que l’apprenant n’a pas validé de nouveau test."
                    ),
                },
            ],
            "automation": {
                "ai_provider": "openai",
                "premium_frequency": "daily",
                "free_frequency": "twice_per_week",
                "outputs": [
                    "Exercices similaires ciblant la même compétence",
                    "Tests de validation supplémentaires sur les erreurs identifiées",
                    "Suggestions regroupées par concept pour suivre la progression",
                ],
            },
            "premium_layer": {
                "label": "Suggestions ciblées par type d’erreur",
                "description": (
                    "Analyse automatique du type d’erreur (concept, compétence, format) et priorisation des actions à mener."
                ),
            },
            "kpis": [
                {
                    "id": "recurring_error_rate",
                    "label": "Baisse d’erreurs récurrentes",
                    "metric": "recurring_error_rate_7d",
                    "target": "Tendance à la baisse semaine après semaine",
                }
            ],
            "experiments": [
                {
                    "type": "aggregation_par_concept",
                    "description": (
                        "Comparer l’agrégation des erreurs par concept avec une vue brute pour valider la pertinence du regroupement."
                    ),
                }
            ],
            "next_steps": [
                {
                    "label": "Refaire des exos similaires",
                    "action": "launch_retry_session",
                }
            ],
        }
    ]

    entries = base_entries[:limit]
    total = len(base_entries)

    return {
        "entries": entries,
        "pagination": {
            "limit": limit,
            "returned": len(entries),
            "has_more": total > limit,
            "total": total,
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
    """Return a demo payload describing the smart error journal feature."""

    return _build_error_journal_demo(limit)
