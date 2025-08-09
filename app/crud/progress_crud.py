# Fichier: backend/app/crud/progress_crud.py (ARCHITECTURE FINALE COMPLÈTE)
import logging
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
from app.models import (
    user_model,
    knowledge_component_model,
    user_knowledge_strength_model,
    user_answer_log_model,
    chapter_model,
    level_model
)
from app.schemas import progress_schema
from app.core import ai_service

logger = logging.getLogger(__name__)

# ==============================================================================
# TÂCHE DE FOND POUR L'ANALYSE PAR L'IA
# ==============================================================================
def analyze_complex_answer_task(db: Session, answer_log_id: int):
    """
    Tâche asynchrone pour analyser une réponse complexe (essai, discussion)
    en utilisant le service IA.
    """
    logger.info(f"ANALYSE IA : Démarrage pour la réponse ID: {answer_log_id}")
    # On charge la réponse et toutes les relations nécessaires pour le contexte
    answer_log = db.query(user_answer_log_model.UserAnswerLog).options(
        joinedload(user_answer_log_model.UserAnswerLog.knowledge_component)
        .joinedload(knowledge_component_model.KnowledgeComponent.chapter)
        .joinedload(chapter_model.Chapter.level)
        .joinedload(level_model.Level.course)
    ).filter(user_answer_log_model.UserAnswerLog.id == answer_log_id).first()

    if not answer_log:
        logger.error(f"ANALYSE IA : Tâche annulée, réponse {answer_log_id} non trouvée.")
        return

    component = answer_log.knowledge_component
    user_answer = answer_log.user_answer_json
    model_choice = component.chapter.level.course.model_choice
    
    feedback_data = {}
    component_type = component.component_type.lower()

    try:
        if component_type in ["essai", "essay", "rédaction", "writing"]:
            feedback_data = ai_service.analyze_user_essay(
                prompt=component.content_json.get("prompt", "Sujet non défini"),
                guidelines=component.content_json.get("guidelines", "Aucune consigne spécifique"),
                user_essay=user_answer.get("text", ""),
                model_choice=model_choice
            )
        # (Vous ajouterez ici la logique pour 'discussion' plus tard)
        # elif component_type == "discussion":
        #     feedback_data = ai_service.start_debate(...)
        
        # Mise à jour de la réponse avec le feedback de l'IA
        answer_log.ai_feedback = feedback_data
        # On met à jour le statut basé sur le retour de l'IA
        if feedback_data.get("is_validated", False):
            answer_log.status = 'correct' 
        else:
            answer_log.status = 'incorrect'
        
        db.commit()
        logger.info(f"ANALYSE IA : Succès pour la réponse {answer_log_id}. Statut final: {answer_log.status}")

        # OPTIONNEL : Mettre à jour la force de mémorisation (SRS) ici après analyse
        # update_knowledge_strength(db, answer_log.user, component, answer_log.status == 'correct')

    except Exception as e:
        logger.error(f"ANALYSE IA : Échec pour la réponse {answer_log_id}. Erreur: {e}", exc_info=True)
        answer_log.status = 'failed' # Un nouveau statut pour les erreurs d'analyse
        answer_log.ai_feedback = {"error": "L'analyse par l'IA a échoué."}
        db.commit()


# ==============================================================================
# FONCTION PRINCIPALE DE TRAITEMENT DE LA RÉPONSE
# ==============================================================================
def process_user_answer(db: Session, user: user_model.User, answer_in: progress_schema.AnswerCreate, background_tasks):
    """
    Traite la soumission d'une réponse par un utilisateur.
    - Corrige instantanément les exercices simples.
    - Lance une tâche de fond pour les exercices complexes.
    """
    component = db.get(knowledge_component_model.KnowledgeComponent, answer_in.component_id)
    if not component:
        return {"status": "error", "feedback": "Composant d'exercice non trouvé."}

    component_type = component.component_type.lower()
    user_answer_json = answer_in.user_answer_json

    # --- Catégorie 1: Exercices Simples (Correction Immédiate) ---
    if component_type in ["qcm", "quiz", "fill_in_the_blank", "reorder"]:
        is_correct = False
        feedback = "Ce n'est pas tout à fait ça. Réessayez !"

        # Exemple pour QCM:
        if component_type == "qcm":
            correct_index = component.content_json.get("correct_option_index")
            is_correct = (correct_index is not None and correct_index == user_answer_json.get("selected_option"))
        
        status = "correct" if is_correct else "incorrect"
        if is_correct:
            feedback = "Bonne réponse !"

        answer_log = user_answer_log_model.UserAnswerLog(
            user_id=user.id, component_id=component.id, status=status,
            user_answer_json=user_answer_json
        )
        db.add(answer_log)
        update_knowledge_strength(db, user, component, is_correct)
        db.commit()
        
        return {"status": status, "feedback": feedback}

    # --- Catégorie 2: Exercices Complexes (Analyse par l'IA) ---
    elif component_type in ["essai", "essay", "rédaction", "writing", "discussion"]:
        answer_log = user_answer_log_model.UserAnswerLog(
            user_id=user.id, component_id=component.id, status="pending_review",
            user_answer_json=user_answer_json
        )
        db.add(answer_log)
        db.commit()
        db.refresh(answer_log)

        # On lance l'analyse en arrière-plan
        background_tasks.add_task(analyze_complex_answer_task, db, answer_log.id)
        
        return {
            "status": "pending_review",
            "feedback": "Votre réponse a été soumise. L'analyse par l'IA est en cours..."
        }
    
    else:
        return {"status": "error", "feedback": "Type d'exercice non géré."}

def add_message_to_discussion(db: Session, answer_log_id: int, user: user_model.User, history: list, user_message: str):
    """
    Gère un nouveau message dans une discussion, appelle l'IA et met à jour le log.
    """
    answer_log = db.get(user_answer_log_model.UserAnswerLog, answer_log_id)
    if not answer_log or answer_log.user_id != user.id:
        return None

    component = answer_log.knowledge_component
    model_choice = component.chapter.level.course.model_choice

    ai_response = ai_service.continue_ai_discussion(
        prompt=component.content_json.get("prompt"),
        history=history,
        user_message=user_message,
        model_choice=model_choice
    )

    new_history = history + [
        {"author": "user", "message": user_message},
        {"author": "ia", "message": ai_response.get("response_text")}
    ]
    
    if not answer_log.ai_feedback:
        answer_log.ai_feedback = {}
    answer_log.ai_feedback["history"] = new_history
    
    if ai_response.get("is_complete", False):
        answer_log.status = 'correct'
        logger.info(f"Discussion {answer_log_id} marquée comme terminée par l'IA.")
        update_knowledge_strength(db, user, component, True)

    db.commit()
    db.refresh(answer_log)
    return answer_log

# ==============================================================================
# FONCTION UTILITAIRE POUR LE SYSTÈME DE RÉPÉTITION ESPACÉE (SRS)
# ==============================================================================
def update_knowledge_strength(db: Session, user: user_model.User, component: knowledge_component_model.KnowledgeComponent, is_correct: bool):
    """
    Met à jour la force de mémorisation de l'utilisateur pour un composant donné.
    """
    strength_entry = db.query(user_knowledge_strength_model.UserKnowledgeStrength).filter_by(
        user_id=user.id, component_id=component.id
    ).first()

    if not strength_entry:
        strength_entry = user_knowledge_strength_model.UserKnowledgeStrength(
            user_id=user.id, component_id=component.id
        )
        db.add(strength_entry)

    strength_entry.last_reviewed_at = datetime.now(timezone.utc)
    current_streak = strength_entry.review_streak or 0
    current_strength = strength_entry.strength or 0.0

    if is_correct:
        strength_entry.review_streak = current_streak + 1
        interval_days = 2 ** strength_entry.review_streak
        strength_entry.next_review_at = datetime.now(timezone.utc) + timedelta(days=interval_days)
        strength_entry.strength = min(1.0, current_strength + 0.1)
    else:
        strength_entry.review_streak = 0
        strength_entry.next_review_at = datetime.now(timezone.utc) + timedelta(hours=4)
        strength_entry.strength = max(0.0, current_strength - 0.2)

    logger.info(f"SRS Update: User {user.id}, Component {component.id}, Correct: {is_correct}, New Strength: {strength_entry.strength}")