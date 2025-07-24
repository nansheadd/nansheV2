# Fichier: nanshe/backend/app/api/v2/endpoints/level_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas import level_schema
from app.crud import level_crud
from app.api.v2.dependencies import get_db

router = APIRouter()

@router.get("/{course_id}/levels/{level_order}", response_model=level_schema.Level)
def read_or_create_level_content(
    course_id: int,
    level_order: int,
    db: Session = Depends(get_db)
):
    """
    Récupère le contenu d'un niveau.
    Si le contenu n'a jamais été accédé, il est généré par l'IA à la volée.
    """
    level = level_crud.get_level_content(db, course_id=course_id, level_order=level_order)
    if not level:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Level not found for this course")
    return level