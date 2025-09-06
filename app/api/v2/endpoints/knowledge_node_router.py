# Fichier: backend/app/api/v2/endpoints/knowledge_node_router.py

import logging # <-- AJOUT : Pour pouvoir utiliser logger.info
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc

from app.api.v2.dependencies import get_db
from app.models.course.knowledge_graph_model import KnowledgeNode
from app.schemas.course.knowledge_graph_schema import KnowledgeNode as KnowledgeNodeSchema
from app.services.tasks import generate_programming_node_content_task

from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.schemas.course.knowledge_component_schema import UserAnswer

router = APIRouter()
logger = logging.getLogger(__name__) # <-- AJOUT : Initialisation du logger

@router.get("/{node_id}", response_model=KnowledgeNodeSchema)
def read_knowledge_node(
    node_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # On récupère l'utilisateur connecté
    current_user: User = Depends(get_current_user)
):
    """
    Récupère le contenu détaillé d'un nœud de connaissance,
    en incluant les réponses précédentes de l'utilisateur pour chaque exercice.
    """
    node = db.query(KnowledgeNode).options(
        selectinload(KnowledgeNode.exercises),
        selectinload(KnowledgeNode.course)
    ).filter(KnowledgeNode.id == node_id).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Nœud de connaissance non trouvé.")
    
    # --- LOGIQUE POUR ATTACHER LES RÉPONSES PRÉCÉDENTES ---
    exercise_ids = [ex.id for ex in node.exercises]
    if exercise_ids:
        # On cherche la dernière réponse de l'utilisateur pour chaque exercice de ce nœud
        latest_answers = db.query(UserAnswerLog).filter(
            UserAnswerLog.user_id == current_user.id,
            UserAnswerLog.node_exercise_id.in_(exercise_ids)
        ).order_by(
            UserAnswerLog.node_exercise_id,
            desc(UserAnswerLog.answered_at)
        ).distinct(UserAnswerLog.node_exercise_id).all()
        
        answers_map = {log.node_exercise_id: log for log in latest_answers}

        # On attache la réponse trouvée à chaque objet exercice
        for exercise in node.exercises:
            if exercise.id in answers_map:
                log = answers_map[exercise.id]
                exercise.user_answer = UserAnswer(
                    id=log.id,
                    status=log.status,
                    is_correct=(log.status == 'correct'),
                    user_answer_json=log.user_answer_json,
                    ai_feedback=log.ai_feedback
                )
    # ---------------------------------------------------------
    
    if node.course and node.course.course_type == "PROGRAMMING" and not node.content_json:
        logger.info(f"Déclenchement de la génération JIT pour le nœud ID {node.id}")
        background_tasks.add_task(generate_programming_node_content_task, node.id)
    
    return node