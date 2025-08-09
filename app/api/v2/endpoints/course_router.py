# Fichier: backend/app/api/v2/endpoints/course_router.py (VERSION FINALE)
from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.schemas import course_schema, personalization_schema
from app.core import ai_service
from app.crud import course_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user_model import User

router = APIRouter()

@router.post("/", response_model=course_schema.Course, status_code=status.HTTP_202_ACCEPTED)
def create_new_course(
    course_in: course_schema.CourseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accepte une nouvelle demande de cours et lance la génération en arrière-plan.
    """
    course = course_crud.create_course(db=db, course_in=course_in, creator=current_user)
    background_tasks.add_task(
        course_crud.generate_course_content_task,
        db=db,
        course_id=course.id,
        creator_id=current_user.id
    )
    return course


@router.post("/personalization-form", response_model=personalization_schema.PersonalizationForm)
def get_personalization_form(
    course_in: course_schema.CourseCreate
):
    """
    Étape 1 : Classifie le sujet.
    Étape 2 : Génère le formulaire de personnalisation adapté au sujet et à la catégorie.
    """
    category = ai_service.classify_course_topic(
        title=course_in.title, model_choice=course_in.model_choice
    )

    # --- LIGNE MODIFIÉE ---
    # On passe maintenant le 'title' à la fonction de génération des questions
    form_data = ai_service.generate_personalization_questions(
        title=course_in.title, # <-- Ajout crucial
        category=category, 
        model_choice=course_in.model_choice
    )
    # --------------------
    
    return {"category": category, "fields": form_data.get("fields", [])}

@router.get("/my-courses", response_model=List[course_schema.Course])
def read_user_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des cours de l'utilisateur connecté."""
    courses = course_crud.get_user_courses(db, user_id=current_user.id)
    return courses

@router.get("/public", response_model=List[course_schema.Course])
def read_public_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère la liste des cours publics disponibles pour l'inscription."""
    courses = course_crud.get_public_courses(db, user_id=current_user.id)
    return courses

@router.get("/{course_id}", response_model=course_schema.Course)
def read_course(course_id: int, db: Session = Depends(get_db)):
    """Récupère les détails d'un cours spécifique par son ID."""
    db_course = course_crud.get_course(db, course_id=course_id)
    if db_course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return db_course

@router.post("/{course_id}/enroll", status_code=status.HTTP_201_CREATED)
def enroll_in_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Inscrit l'utilisateur connecté à un cours."""
    course = course_crud.get_course(db, course_id=course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course_crud.enroll_user_in_course(db, course_id=course_id, user_id=current_user.id)
    return {"message": "Inscription réussie"}

@router.post("/{course_id}/unenroll", status_code=status.HTTP_200_OK)
def unenroll_from_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Désinscrit l'utilisateur connecté d'un cours."""
    success = course_crud.unenroll_user_from_course(db, course_id=course_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Inscription non trouvée")
    return {"message": "Désinscription réussie"}