# Fichier: backend/app/api/v2/endpoints/chapter_router.py (VERSION FINALE SÉCURISÉE)
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.schemas import chapter_schema
from app.crud import chapter_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models import chapter_model, user_model, knowledge_component_model, user_answer_log_model

router = APIRouter()

@router.get("/{chapter_id}", response_model=chapter_schema.Chapter)
def read_chapter_details(
    chapter_id: int, 
    db: Session = Depends(get_db), 
    current_user: user_model.User = Depends(get_current_user)
):
    """
    Récupère les détails d'un chapitre et attache de manière sécurisée la dernière
    réponse de l'utilisateur connecté pour chaque exercice.
    """
    # Étape 1 : Récupérer le contenu du chapitre (identique pour tous les utilisateurs)
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.knowledge_components)
    ).filter(chapter_model.Chapter.id == chapter_id).first()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Étape 2 : Récupérer de manière isolée les réponses de l'utilisateur connecté
    component_ids = [comp.id for comp in chapter.knowledge_components]
    
    if not component_ids:
        # Si le chapitre n'a pas encore d'exercices, on retourne directement les données
        return chapter_schema.Chapter.from_orm(chapter)

    # Sous-requête pour trouver la dernière réponse pour chaque composant
    latest_answers_subquery = db.query(
        user_answer_log_model.UserAnswerLog.component_id,
        user_answer_log_model.UserAnswerLog.is_correct,
        user_answer_log_model.UserAnswerLog.user_answer_json
    ).filter(
        user_answer_log_model.UserAnswerLog.user_id == current_user.id,
        user_answer_log_model.UserAnswerLog.component_id.in_(component_ids)
    ).order_by(
        user_answer_log_model.UserAnswerLog.component_id,
        desc(user_answer_log_model.UserAnswerLog.answered_at)
    ).distinct(
        user_answer_log_model.UserAnswerLog.component_id
    ).subquery()

    # On transforme les résultats en un dictionnaire pour un accès facile : {component_id: answer}
    user_answers_map = {
        row.component_id: {
            "is_correct": row.is_correct,
            "user_answer_json": row.user_answer_json
        }
        for row in db.query(latest_answers_subquery).all()
    }

    # Étape 3 : Construire l'objet de réponse final
    response_chapter = chapter_schema.Chapter.from_orm(chapter)
    
    for component_schema in response_chapter.knowledge_components:
        if component_schema.id in user_answers_map:
            component_schema.user_answer = user_answers_map[component_schema.id]

    return response_chapter


# --- Les autres routes (POST pour la génération) ne changent pas ---

@router.post("/{chapter_id}/generate-lesson", status_code=status.HTTP_202_ACCEPTED)
def trigger_lesson_generation(
    chapter_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Lance la génération de la leçon pour un chapitre en tâche de fond.
    Permet de relancer la tâche si elle a échoué ou est bloquée.
    """
    chapter = db.get(chapter_model.Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
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
    db: Session = Depends(get_db)
):
    """
    Lance la génération des exercices pour un chapitre en tâche de fond.
    """
    chapter = db.get(chapter_model.Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    if chapter.exercises_status == "completed":
        return {"message": "Les exercices ont déjà été générés."}
    if chapter.lesson_status != "completed":
        raise HTTPException(status_code=400, detail="La leçon doit être terminée avant de générer les exercices.")

    chapter.exercises_status = "generating"
    db.commit()
    
    background_tasks.add_task(chapter_crud.generate_exercises_task, db, chapter_id)
    return {"message": "La génération des exercices a commencé (ou a été relancée)."}