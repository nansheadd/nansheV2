# Fichier: backend/app/api/v2/endpoints/course_router.py (CORRIGÉ)
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas import course_schema
from app.crud import course_crud
from app.api.v2.dependencies import get_db, get_current_user # On importe get_current_user
from app.models.user_model import User # On importe le modèle User

router = APIRouter()

@router.post("/", response_model=course_schema.Course, status_code=status.HTTP_201_CREATED)
def create_new_course(
    course_in: course_schema.CourseCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # <-- 1. On récupère l'utilisateur connecté
):
    """
    Crée un nouveau cours et inscrit automatiquement son créateur.
    """
    # 2. On passe l'utilisateur à la fonction de création
    course = course_crud.create_course(db=db, course_in=course_in, creator=current_user)
    return course

@router.get("/", response_model=List[course_schema.Course])
def read_courses(db: Session = Depends(get_db)):
    """Récupère la liste de tous les cours."""
    courses = course_crud.get_courses(db)
    return courses

@router.get("/{course_id}", response_model=course_schema.Course)
def read_course(course_id: int, db: Session = Depends(get_db)):
    """Récupère les détails d'un cours spécifique par son ID."""
    db_course = course_crud.get_course(db, course_id=course_id)
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course