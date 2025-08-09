# Fichier: backend/app/crud/progress_crud.py (ARCHITECTURE FINALE COMPLÈTE)
import logging
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, timedelta, timezone
from app.models import (
    user_model,
    knowledge_component_model,
    user_knowledge_strength_model,
    user_answer_log_model,
    chapter_model,
    level_model,
    user_topic_performance_model
)
from app.schemas import progress_schema
from app.core import ai_service

logger = logging.getLogger(__name__)

# ==============================================================================
# FONCTIONS UTILITAIRES (STATS & SRS)
# ==============================================================================

def update_topic_performance(db: Session, user: user_model.User, component: knowledge_component_model.KnowledgeComponent, is_correct: bool):
    """
    Trouve ou crée une entrée de performance pour un sujet (catégorie) et la met à jour.
    """
    topic_category = component.category
    course_id = component.chapter.level.course_id

    performance = db.query(user_topic_performance_model.UserTopicPerformance).filter_by(
        user_id=user.id,
        course_id=course_id,
        topic_category=topic_category
    ).first()

    if not performance:
        performance = user_topic_performance_model.UserTopicPerformance(
            user_id=user.id,
            course_id=course_id,
            topic_category=topic_category,
            correct_answers=0,
            incorrect_answers=0,
            total_attempts=0,
            mastery_score=0.0
        )
        db.add(performance)

    performance.total_attempts += 1
    if is_correct:
        performance.correct_answers += 1
    else:
        performance.incorrect_answers += 1
    
    if performance.total_attempts > 0:
        performance.mastery_score = performance.correct_answers / performance.total_attempts
    
    logger.info(f"STATISTIQUES: User {user.id}, Sujet '{topic_category}', Score: {performance.mastery_score:.2f}")

def update_knowledge_strength(db: Session, user: user_model.User, component: knowledge_component_model.KnowledgeComponent, is_correct: bool):
    """Met à jour la force de mémorisation de l'utilisateur pour un composant donné (SRS)."""
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

# ==============================================================================
# TÂCHE DE FOND POUR L'ANALYSE PAR L'IA
# ==============================================================================
def analyze_complex_answer_task(db: Session, answer_log_id: int):
    """Tâche asynchrone pour analyser une réponse complexe (essai, discussion) via l'IA."""
    logger.info(f"ANALYSE IA : Démarrage pour la réponse ID: {answer_log_id}")
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
                prompt=component.content_json.get("prompt", ""),
                guidelines=component.content_json.get("guidelines", ""),
                user_essay=user_answer.get("text", ""),
                model_choice=model_choice
            )
        elif component_type == "discussion":
            feedback_data = ai_service.start_ai_discussion(
                prompt=component.content_json.get("prompt", ""),
                user_first_post=user_answer.get("text", ""),
                model_choice=model_choice
            )
        
        is_validated = feedback_data.get("is_validated", False)
        answer_log.ai_feedback = feedback_data
        answer_log.status = 'correct' if is_validated else 'incorrect'
        
        # On met à jour les stats et le SRS APRÈS l'analyse de l'IA
        update_topic_performance(db, answer_log.user, component, is_validated)
        update_knowledge_strength(db, answer_log.user, component, is_validated)
        
        db.commit()
        logger.info(f"ANALYSE IA : Succès pour la réponse {answer_log_id}. Statut final: {answer_log.status}")

    except Exception as e:
        logger.error(f"ANALYSE IA : Échec pour la réponse {answer_log_id}. Erreur: {e}", exc_info=True)
        answer_log.status = 'failed'
        answer_log.ai_feedback = {"error": "L'analyse par l'IA a échoué."}
        db.commit()


# ==============================================================================
# FONCTION DE CONTINUATION DE DISCUSSION
# ==============================================================================
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

    # --- CORRECTION DÉFINITIVE ---
    # On notifie explicitement SQLAlchemy que le champ JSON a été modifié.
    flag_modified(answer_log, "ai_feedback")
    # ---------------------------

    db.commit()
    db.refresh(answer_log)
    return answer_log

# ==============================================================================
# FONCTION PRINCIPALE DE TRAITEMENT DE LA RÉPONSE
# ==============================================================================
def process_user_answer(db: Session, user: user_model.User, answer_in: progress_schema.AnswerCreate, background_tasks):
    """
    Traite la soumission d'une réponse, corrige les exercices simples et lance
    les tâches de fond pour les exercices complexes.
    """
    component = db.query(knowledge_component_model.KnowledgeComponent).options(
        joinedload(knowledge_component_model.KnowledgeComponent.chapter)
        .joinedload(chapter_model.Chapter.level)
    ).filter(knowledge_component_model.KnowledgeComponent.id == answer_in.component_id).first()

    if not component:
        return {"status": "error", "feedback": "Composant d'exercice non trouvé."}

    component_type = component.component_type.lower()
    user_answer_json = answer_in.user_answer_json
    content_json = component.content_json

    if component_type in ["qcm", "quiz", "fill_in_the_blank", "reorder"]:
        is_correct = False
        feedback = "Ce n'est pas tout à fait ça. Réessayez !"

        if component_type == "qcm":
            correct_index = content_json.get("correct_option_index")
            is_correct = correct_index is not None and correct_index == user_answer_json.get("selected_option")
        
        elif component_type == "quiz":
            user_answers = user_answer_json.get("answers", {})
            questions = content_json.get("questions", [])
            if not questions:
                is_correct = False
                feedback = "Le format de ce quiz est invalide."
            else:
                total_questions = len(questions)
                correct_count = sum(1 for i, q in enumerate(questions) if q.get("answer") == user_answers.get(str(i)))
                is_correct = correct_count == total_questions
                feedback = f"Votre score : {correct_count}/{total_questions}. " + ("Parfait !" if is_correct else "Continuez vos efforts !")

        elif component_type == "fill_in_the_blank":
            correct_answers = [str(ans).lower().strip() for ans in content_json.get("answers", [])]
            user_answers = [str(ua).lower().strip() for ua in user_answer_json.get("filled_blanks", [])]
            is_correct = bool(correct_answers and user_answers and correct_answers == user_answers)

        elif component_type == "reorder":
            correct_order = content_json.get("correct_order", [])
            user_order = user_answer_json.get("ordered_items", [])
            is_correct = correct_order == user_order

        status = "correct" if is_correct else "incorrect"
        if is_correct:
            feedback = "Bonne réponse ! Continuez comme ça."
        
        answer_log = user_answer_log_model.UserAnswerLog(
            user_id=user.id, component_id=component.id, status=status,
            user_answer_json=user_answer_json
        )
        db.add(answer_log)
        
        update_knowledge_strength(db, user, component, is_correct)
        update_topic_performance(db, user, component, is_correct)
        
        db.commit()
        return {"status": status, "feedback": feedback}

    elif component_type in ["essai", "essay", "rédaction", "writing", "discussion"]:
        answer_log = user_answer_log_model.UserAnswerLog(
            user_id=user.id, component_id=component.id, status="pending_review",
            user_answer_json=user_answer_json
        )
        db.add(answer_log)
        db.commit()
        db.refresh(answer_log)
        background_tasks.add_task(analyze_complex_answer_task, db, answer_log.id)
        return {"status": "pending_review", "feedback": "Votre réponse a été soumise pour analyse..."}
    
    else:
        return {"status": "error", "feedback": f"Type d'exercice '{component.component_type}' non géré."}