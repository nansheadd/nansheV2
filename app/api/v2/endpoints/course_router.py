# Fichier: backend/app/api/v2/endpoints/course_router.py (VERSION FINALE)
from app.schemas.course import course_schema
from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.schemas.progress import personalization_schema
from app.schemas.course import vocabulary_schema
from app.schemas.course import knowledge_graph_schema
from app.models.course.knowledge_graph_model import KnowledgeNode, KnowledgeEdge
from app.models.course.vocabulary_item_model import VocabularyItem
from app.models.course.chapter_model import Chapter
from app.models.course.level_model import Level
from app.core import ai_service
from app.crud.course import course_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User

router = APIRouter()

# Fichier: backend/app/api/v2/endpoints/course_router.py (partiel)



@router.post("/", response_model=course_schema.Course, status_code=status.HTTP_202_ACCEPTED)
def create_new_course(
    course_in: course_schema.CourseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Étape 1 (Synchrone) : Crée la "coquille" du cours et renvoie son ID.
    Étape 2 (Asynchrone) : Lance la génération du plan de cours en arrière-plan.
    """
    # ÉTAPE 1 : On appelle une fonction qui crée JUSTE l'entrée en base de données.
    course = course_crud.create_course_shell(db=db, course_in=course_in, creator=current_user)
    
    # ÉTAPE 2 : On lance la tâche de fond avec l'ID que nous avons maintenant.
    background_tasks.add_task(
        course_crud.generate_course_plan_task,
        course_id=course.id,
        creator_id=current_user.id
    )
    
    # ÉTAPE 3 : On renvoie l'objet cours avec son ID au frontend.
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

   
    form_data = ai_service.generate_personalization_questions(
        title=course_in.title,
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


@router.get("/{course_id}/vocabulary", response_model=List[vocabulary_schema.VocabularyItem])
def get_course_vocabulary(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère tout le vocabulaire d'un cours.
    """
    items = db.query(VocabularyItem).join(Chapter).join(Level).filter(Level.course_id == course_id).all()
    return items


@router.get("/{course_id}/knowledge-graph", response_model=knowledge_graph_schema.KnowledgeGraph)
def read_course_knowledge_graph(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère la structure complète du graphe de connaissances pour un cours.
    """
    course = course_crud.get_course(db, course_id=course_id)
    if not course or course.course_type != 'philosophie':
        raise HTTPException(status_code=404, detail="Graphe de connaissances non trouvé pour ce cours.")

    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.course_id == course_id).all()
    edges = db.query(KnowledgeEdge).join(KnowledgeNode, KnowledgeEdge.source_node_id == KnowledgeNode.id).filter(KnowledgeNode.course_id == course_id).all()

    return {
        "course_title": course.title,
        "nodes": nodes,
        "edges": edges
    }