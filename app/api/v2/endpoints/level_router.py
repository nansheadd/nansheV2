# Fichier: backend/app/api/v2/endpoints/level_router.py (CORRIGÉ)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas import level_schema
from app.crud import level_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user_model import User

router = APIRouter()

@router.get("/{level_id}", response_model=level_schema.Level)
def read_level_details(
    level_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les détails d'un niveau (ses chapitres).
    Génère le plan des chapitres à la volée si nécessaire.
    """
    level = level_crud.get_level_with_chapters(db, level_id=level_id, user_id=current_user.id)
    if not level:
        raise HTTPException(status_code=403, detail="Level not found or access denied")
    return level