# Fichier: backend/app/api/v2/endpoints/chapter_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas import chapter_schema
from app.crud import chapter_crud
from app.api.v2.dependencies import get_db

router = APIRouter()

@router.get("/{chapter_id}", response_model=chapter_schema.Chapter)
def read_chapter_details(chapter_id: int, db: Session = Depends(get_db)):
    """
    Récupère les détails d'un chapitre.
    Génère la leçon et les exercices à la volée si nécessaire.
    """
    chapter = chapter_crud.get_chapter_details(db, chapter_id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter