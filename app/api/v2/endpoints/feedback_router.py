# app/api/v2/endpoints/feedback_router.py

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.models.analytics.feedback_model import ContentFeedback, ContentFeedbackDetail
from app.schemas.analytics import feedback_schema

router = APIRouter()


@router.post("/", response_model=feedback_schema.FeedbackOut, status_code=status.HTTP_201_CREATED)
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
    rating_str = feedback_in.rating  # "liked" | "disliked" | "none"

    fb = (
        db.query(ContentFeedback)
        .filter_by(
            user_id=current_user.id,
            content_id=feedback_in.content_id,
            content_type=feedback_in.content_type,
        )
        .one_or_none()
    )

    if rating_str in (None, "none"):
        if fb:
            if fb.detail:
                db.delete(fb.detail)
            db.delete(fb)
            db.commit()
        return {"id": None, "rating": None, "status": "deleted", "reason_code": None, "comment": None}

    if rating_str not in {"liked", "disliked"}:
        raise HTTPException(status_code=400, detail="rating_invalid")

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
        db.flush([fb])

    if rating_str == "disliked":
        if not (feedback_in.reason_code and feedback_in.comment and feedback_in.comment.strip()):
            raise HTTPException(status_code=400, detail="reason_required")
        if fb.detail:
            fb.detail.reason_code = feedback_in.reason_code
            fb.detail.comment = feedback_in.comment.strip()
        else:
            fb.detail = ContentFeedbackDetail(
                reason_code=feedback_in.reason_code,
                comment=feedback_in.comment.strip(),
            )
    else:
        if fb.detail:
            db.delete(fb.detail)

    db.commit()
    db.refresh(fb)

    detail = fb.detail
    return {
        "id": fb.id,
        "rating": fb.rating,
        "status": fb.status,
        "reason_code": detail.reason_code if detail else None,
        "comment": detail.comment if detail else None,
    }


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
