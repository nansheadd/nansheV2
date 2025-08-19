# app/api/v2/endpoints/feedback_router.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.models.analytics.feedback_model import ContentFeedback
from app.schemas.analytics import feedback_schema

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    feedback_in: feedback_schema.FeedbackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crée ou met à jour le feedback de l'utilisateur courant pour un contenu donné.
    On stocke des *strings* pour `rating` et `status` (pas d'Enum Python côté DB).
    Un nouveau vote remet le statut à 'pending'.
    """
    rating_str = feedback_in.rating  # "liked" | "disliked"

    fb = (
        db.query(ContentFeedback)
        .filter_by(
            user_id=current_user.id,
            content_id=feedback_in.content_id,
            content_type=feedback_in.content_type,
        )
        .one_or_none()
    )

    if fb:
        fb.rating = rating_str
        fb.status = "pending"
    else:
        fb = ContentFeedback(
            user_id=current_user.id,
            content_id=feedback_in.content_id,
            content_type=feedback_in.content_type,
            rating=rating_str,
            status="pending",
        )
        db.add(fb)

    db.commit()
    db.refresh(fb)
    return {"id": fb.id, "rating": fb.rating, "status": fb.status}


@router.post("/status", response_model=feedback_schema.BulkFeedbackStatusOut)
def get_feedback_statuses(
    payload: feedback_schema.BulkFeedbackStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Pour une liste d'IDs de contenu, renvoie le *rating* actuel de l'utilisateur
    (clé = content_id, valeur = "liked" | "disliked").
    """
    if not payload.content_ids:
        return {"statuses": {}}

    feedbacks = (
        db.query(ContentFeedback)
        .filter(
            ContentFeedback.user_id == current_user.id,
            ContentFeedback.content_type == payload.content_type,
            ContentFeedback.content_id.in_(payload.content_ids),
        )
        .all()
    )

    # On renvoie la string directement (le champ DB est un VARCHAR)
    statuses = {fb.content_id: fb.rating for fb in feedbacks if fb.rating}

    return {"statuses": statuses}
