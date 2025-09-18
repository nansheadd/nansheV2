from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_db, get_current_user
from app.crud import badge_crud
from app.schemas.user.badge_schema import BadgeWithStatus
from app.models.user.user_model import User

router = APIRouter()


@router.get("/", response_model=list[BadgeWithStatus], summary="Liste des badges et progression")
async def list_badges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return badge_crud.get_badges_with_status(db, current_user.id)
