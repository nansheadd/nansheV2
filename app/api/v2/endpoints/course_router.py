# Fichier: nanshe/backend/app/api/v2/endpoints/course_router.py
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas import course_schema
from app.crud import course_crud
from app.api.v2.dependencies import get_db

router = APIRouter()

@router.post("/", response_model=course_schema.Course, status_code=status.HTTP_201_CREATED)
def create_new_course(
    course_in: course_schema.CourseCreate, 
    db: Session = Depends(get_db)
):
    """
    Crée un nouveau cours.
    Dans cette version, le plan est généré par un placeholder.
    """
    course = course_crud.create_course(db=db, course_in=course_in)
    return course


@router.get("/{course_id}", response_model=course_schema.Course)
def read_course(course_id: int, db: Session = Depends(get_db)):
    """
    Récupère les détails d'un cours spécifique par son ID.
    """
    db_course = course_crud.get_course(db, course_id=course_id)
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course


@router.get("/", response_model=List[course_schema.Course]) # <--- NOUVEL ENDPOINT
def read_courses(db: Session = Depends(get_db)):
    """Récupère la liste de tous les cours."""
    courses = course_crud.get_courses(db)
    return courses