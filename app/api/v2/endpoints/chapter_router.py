# Fichier: backend/app/api/v2/endpoints/chapter_router.py (ARCHITECTURE FINALE)
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.schemas import chapter_schema, knowledge_component_schema
from app.crud import chapter_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models import chapter_model, user_model, user_answer_log_model

router = APIRouter()

@router.get("/{chapter_id}", response_model=chapter_schema.Chapter)
def read_chapter_details(
    chapter_id: int, 
    db: Session = Depends(get_db), 
    current_user: user_model.User = Depends(get_current_user)
):
    chapter = chapter_crud.get_chapter_details(db, chapter_id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    component_ids = [comp.id for comp in chapter.knowledge_components]
    if not component_ids: return chapter

    # --- REQUÊTE CORRIGÉE : On ajoute l'ID à la sélection ---
    latest_answers_subquery = db.query(
        user_answer_log_model.UserAnswerLog.id, # <-- LA LIGNE CRUCIALE
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
            "id": row.id, # <-- On stocke l'ID
            "status": row.status,
            "is_correct": row.status == 'correct',
            "user_answer_json": row.user_answer_json,
            "ai_feedback": row.ai_feedback
        }
        for row in db.query(latest_answers_subquery).all()
    }
    
    response_chapter = chapter_schema.Chapter.from_orm(chapter)
    
    for comp_schema in response_chapter.knowledge_components:
        if comp_schema.id in user_answers_map:
            comp_schema.user_answer = knowledge_component_schema.UserAnswer(**user_answers_map[comp_schema.id])

    return response_chapter

@router.post("/{chapter_id}/generate-lesson", status_code=status.HTTP_202_ACCEPTED)
def trigger_lesson_generation(
    chapter_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user) # Ajout pour la sécurité
):
    """
    Lance la génération de la leçon pour un chapitre en tâche de fond.
    Permet de relancer la tâche si elle a échoué ou est bloquée.
    """
    chapter = db.get(chapter_model.Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    
    # On pourrait ajouter une vérification pour s'assurer que l'utilisateur a accès à ce cours
    
    if chapter.lesson_status == "completed":
        return {"message": "La leçon a déjà été générée."}
    
    chapter.lesson_status = "generating"
    db.commit()
    
    background_tasks.add_task(chapter_crud.generate_lesson_task, db, chapter_id)
    return {"message": "La génération de la leçon a commencé (ou a été relancée)."}


@router.post("/{chapter_id}/generate-exercises", status_code=status.HTTP_202_ACCEPTED)
def trigger_exercises_generation(
    chapter_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user) # Ajout pour la sécurité
):
    """
    Lance la génération des exercices pour un chapitre en tâche de fond.
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
    return {"message": "La génération des exercices a commencé (ou a été relancée)."}