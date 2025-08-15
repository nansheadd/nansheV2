# Fichier : nanshe/backend/app/api/v2/endpoints/chapter_router.py (VERSION FINALE COMPLÈTE)
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

# On utilise les nouveaux chemins d'importation suite à la réorganisation
from app.schemas.course import chapter_schema, knowledge_component_schema
from app.crud.course import chapter_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.course import chapter_model
from app.models.user.user_model import User
from app.models.progress import user_answer_log_model

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/{chapter_id}", response_model=chapter_schema.Chapter)
def read_chapter_details(
    chapter_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les détails d'un chapitre.
    Si le chapitre appartient à un cours de langue et n'a pas encore été généré,
    cette fonction déclenche la pipeline de génération de contenu JIT en arrière-plan.
    """
    chapter = chapter_crud.get_chapter_details(db, chapter_id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    # --- LOGIQUE D'AIGUILLAGE "JUSTE-À-TEMPS" ---
    is_language_course = chapter.level.course.course_type == 'langue'
    is_content_pending = chapter.lesson_status == "pending"

    if is_language_course and is_content_pending:
        logger.info(f"Déclenchement de la pipeline JIT pour le chapitre de langue {chapter.id}")
        chapter.lesson_status = "generating"
        chapter.exercises_status = "generating"
        db.commit()
        
        # On lance la tâche de fond spécialisée pour les langues
        background_tasks.add_task(chapter_crud.generate_language_chapter_content_task, db, chapter_id)
        
        db.refresh(chapter)
    # ---------------------------------------------

    # --- Récupération des dernières réponses de l'utilisateur (logique existante) ---
    component_ids = [comp.id for comp in chapter.knowledge_components]
    if not component_ids:
        return chapter_schema.Chapter.model_validate(chapter)

    latest_answers_subquery = db.query(
        user_answer_log_model.UserAnswerLog.id,
        user_answer_log_model.UserAnswerLog.component_id,
        user_answer_log_model.UserAnswerLog.status,
        user_answer_log_model.UserAnswerLog.user_answer_json,
        user_answer_log_model.UserAnswerLog.ai_feedback
    ).filter(
        user_answer_log_model.UserAnswerLog.user_id == current_user.id,
        user_answer_log_model.UserAnswerLog.component_id.in_(component_ids)
    ).order_by(
        user_answer_log_model.UserAnswerLog.component_id,
        desc(user_answer_log_model.UserAnswerLog.answered_at)
    ).distinct(user_answer_log_model.UserAnswerLog.component_id).subquery()

    user_answers_map = {
        row.component_id: {
            "id": row.id,
            "status": row.status,
            "is_correct": row.status == 'correct',
            "user_answer_json": row.user_answer_json,
            "ai_feedback": row.ai_feedback
        }
        for row in db.query(latest_answers_subquery).all()
    }
    
    response_chapter = chapter_schema.Chapter.model_validate(chapter)
    
    for comp_schema in response_chapter.knowledge_components:
        if comp_schema.id in user_answers_map:
            comp_schema.user_answer = knowledge_component_schema.UserAnswer(**user_answers_map[comp_schema.id])

    return response_chapter


@router.post("/{chapter_id}/generate-lesson", status_code=status.HTTP_202_ACCEPTED)
def trigger_lesson_generation(
    chapter_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    [POUR COURS NON-LINGUISTIQUES] Lance la génération de la leçon pour un chapitre.
    """
    chapter = db.get(chapter_model.Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    
    if chapter.lesson_status == "completed":
        return {"message": "La leçon a déjà été générée."}
    
    chapter.lesson_status = "generating"
    db.commit()
    
    background_tasks.add_task(chapter_crud.generate_lesson_task, db, chapter_id)
    return {"message": "La génération de la leçon a commencé."}


@router.post("/{chapter_id}/generate-exercises", status_code=status.HTTP_202_ACCEPTED)
def trigger_exercises_generation(
    chapter_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    [POUR COURS NON-LINGUISTIQUES] Lance la génération des exercices pour un chapitre.
    """
    chapter = db.get(chapter_model.Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    
    if chapter.exercises_status == "completed":
        return {"message": "Les exercices ont déjà été générés."}
    if chapter.lesson_status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La leçon doit être terminée avant de générer les exercices.")

    chapter.exercises_status = "generating"
    db.commit()
    
    background_tasks.add_task(chapter_crud.generate_exercises_task, db, chapter_id)
    return {"message": "La génération des exercices a commencé."}