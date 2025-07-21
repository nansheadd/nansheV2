# Fichier: nanshe/backend/app/api/v2/endpoints/course_router.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.schemas import course_schema
from app.crud import course_crud
from app.api.v2.dependencies import get_db

router = APIRouter()

@router.post("/courses", response_model=course_schema.Course, status_code=status.HTTP_201_CREATED)
def create_new_course(
    course_in: course_schema.CourseCreate, 
    db: Session = Depends(get_db)
):
    """
    Crée un nouveau cours.
    Dans cette version, le plan est généré par un placeholder.
    """
    course = course_crud.create_course(db=db, course=course_in)
    return course