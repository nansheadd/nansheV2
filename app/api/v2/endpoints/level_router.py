# Fichier: nanshe/backend/app/api/v2/endpoints/level_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas import level_schema
from app.crud import level_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user_model import User

router = APIRouter()

@router.get("/{course_id}/levels/{level_order}", response_model=level_schema.Level)
def read_or_create_level_content(
    course_id: int, level_order: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # On récupère l'utilisateur connecté
):
    level = level_crud.get_level_content(db, course_id=course_id, level_order=level_order, user_id=current_user.id)
    if not level:
        raise HTTPException(status_code=403, detail="Level not found or access denied")
    return level