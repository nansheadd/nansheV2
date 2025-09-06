# Fichier : nanshe/backend/app/api/v2/endpoints/chapter_router.py (VERSION MISE À JOUR)
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

# On utilise les nouveaux chemins d'importation suite à la réorganisation
from app.schemas.course import chapter_schema, knowledge_component_schema
# NOUVEAUX IMPORTS POUR LES SCHÉMAS DE VOCABULAIRE ET CARACTÈRES
from app.schemas.course import vocabulary_schema, character_schema
from app.crud.course import chapter_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.course import chapter_model
from app.models.user.user_model import User
from app.models.progress import user_answer_log_model
from typing import List

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
    Récupère les détails d'un chapitre et déclenche la génération de contenu
    "Juste-à-Temps" (JIT) si le contenu n'a pas encore été créé.
    """
    chapter = chapter_crud.get_chapter_details(db, chapter_id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    # --- DÉCLENCHEUR JIT UNIFIÉ ---
    if chapter.lesson_status == "pending":
        logger.info(f"Déclenchement JIT pour le chapitre '{chapter.title}' (ID: {chapter.id})")
        chapter.lesson_status = "generating"
        chapter.exercises_status = "generating"
        db.commit()
        
        # Aiguillage : on choisit la bonne fonction de génération en fonction du type de cours
        course_type = chapter.level.course.course_type
        if course_type == 'langue':
            logger.info(f"  -> Tâche de génération de langue sélectionnée.")
            task_function = chapter_crud.generate_language_chapter_content_task
        else:
            logger.info(f"  -> Tâche de génération générique sélectionnée.")
            task_function = chapter_crud.generate_generic_chapter_content_task
        
        # On lance la tâche de fond correspondante
        background_tasks.add_task(
            task_function, 
            db=db, 
            chapter_id=chapter_id,
            user_id=current_user.id
        )
        db.refresh(chapter)
    
    # --- PRÉPARATION DE LA RÉPONSE ---
    # Valide l'objet chapter de base avec Pydantic
    response_chapter = chapter_schema.Chapter.model_validate(chapter)

    # Récupère le vocabulaire et les caractères pour les cours de langue
    if chapter.level.course.course_type == 'langue':
        response_chapter.characters = chapter_crud.get_characters_with_strength(db, chapter_id=chapter_id, user_id=current_user.id)
        response_chapter.vocabulary = chapter_crud.get_vocabulary_with_strength(db, chapter_id=chapter_id, user_id=current_user.id)

    # Récupère les dernières réponses de l'utilisateur pour les exercices du chapitre
    component_ids = [comp.id for comp in chapter.knowledge_components]
    if component_ids:
        latest_answers_query = db.query(
            user_answer_log_model.UserAnswerLog
        ).filter(
            user_answer_log_model.UserAnswerLog.user_id == current_user.id,
            user_answer_log_model.UserAnswerLog.component_id.in_(component_ids)
        ).order_by(
            user_answer_log_model.UserAnswerLog.component_id,
            desc(user_answer_log_model.UserAnswerLog.answered_at)
        ).distinct(user_answer_log_model.UserAnswerLog.component_id)
        
        user_answers_map = {log.component_id: log for log in latest_answers_query.all()}
        
        for comp_schema in response_chapter.knowledge_components:
            if comp_schema.id in user_answers_map:
                log = user_answers_map[comp_schema.id]
                comp_schema.user_answer = knowledge_component_schema.UserAnswer(
                    id=log.id,
                    status=log.status,
                    is_correct=(log.status == 'correct'),
                    user_answer_json=log.user_answer_json,
                    ai_feedback=log.ai_feedback
                )

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