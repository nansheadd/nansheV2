from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user, get_db
from app.models.user.user_model import User
from app.schemas.vote import feature_vote_schema
from app.services.feature_vote_service import FeatureVoteError, FeatureVoteService

router = APIRouter()


@router.get("/current", response_model=feature_vote_schema.FeaturePollOut)
def get_active_feature_poll(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FeatureVoteService(db=db, user=current_user)
    poll = service.get_active_poll()
    if not poll:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_active_poll")
    return service.build_poll_payload(poll)


@router.post("/{poll_id}/votes", response_model=feature_vote_schema.FeaturePollOut)
def submit_feature_votes(
    poll_id: int,
    payload: feature_vote_schema.FeaturePollVoteIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FeatureVoteService(db=db, user=current_user)
    allocations = {item.option_id: item.votes for item in payload.allocations}
    try:
        poll = service.submit_votes(poll_id=poll_id, allocations=allocations)
    except FeatureVoteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return service.build_poll_payload(poll)
