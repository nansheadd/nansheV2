# Fichier: backend/app/crud/progress_crud.py

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.models import user_model, knowledge_component_model, user_knowledge_strength_model, user_answer_log_model
from app.schemas import progress_schema
import logging

logger = logging.getLogger(__name__)

def process_user_answer(db: Session, user: user_model.User, answer_in: progress_schema.AnswerCreate):
    """
    Traite la réponse d'un utilisateur, met à jour sa force et enregistre la réponse.
    """
    component = db.get(knowledge_component_model.KnowledgeComponent, answer_in.component_id)
    if not component:
        return {"is_correct": False, "feedback": "Composant de connaissance non trouvé."}

    is_correct = False

    # --- Logique d'Évaluation par Type d'Exercice ---
    component_type = component.component_type
    content = component.content_json
    user_answer = answer_in.user_answer_json

    if component_type == "qcm":
        is_correct = (content.get("correct_option_index") == user_answer.get("selected_option"))

    elif component_type == "fill_in_the_blank":
        correct_answers = content.get("answers", [])
        user_answers = user_answer.get("filled_blanks", [])
        is_correct = (len(correct_answers) == len(user_answers) and 
                      all(c.lower().strip() == u.lower().strip() for c, u in zip(correct_answers, user_answers)))

    elif component_type == "reorder":
        correct_order = content.get("items", [])
        user_order = user_answer.get("ordered_items", [])
        is_correct = (correct_order == user_order)

    elif component_type == "categorization":
        try:
            correct_mapping = {item['text']: item['category'] for item in content.get("items", [])}
            user_mapping = user_answer.get("categorized_items", {})
            is_correct = (correct_mapping == user_mapping)
        except Exception:
            is_correct = False

    # --- Fin de la Logique d'Évaluation ---

    # Enregistrement de la réponse dans l'historique
    answer_log = user_answer_log_model.UserAnswerLog(
        user_id=user.id,
        component_id=component.id,
        is_correct=is_correct,
        user_answer_json=answer_in.user_answer_json
    )
    db.add(answer_log)

    # Mise à jour de la force de l'utilisateur (algorithme SRS)
    strength_entry = db.query(user_knowledge_strength_model.UserKnowledgeStrength).filter_by(
        user_id=user.id, component_id=component.id
    ).first()

    if not strength_entry:
        strength_entry = user_knowledge_strength_model.UserKnowledgeStrength(
            user_id=user.id, component_id=component.id
        )
        db.add(strength_entry)

    strength_entry.last_reviewed_at = datetime.now(timezone.utc)
    
    if is_correct:
        current_streak = strength_entry.review_streak or 0
        strength_entry.review_streak = current_streak + 1
        interval_days = 2 ** strength_entry.review_streak
        strength_entry.next_review_at = datetime.now(timezone.utc) + timedelta(days=interval_days)
        current_strength = strength_entry.strength or 0.0
        strength_entry.strength = min(1.0, current_strength + 0.1)
    else:
        strength_entry.review_streak = 0
        strength_entry.next_review_at = datetime.now(timezone.utc) + timedelta(hours=4)
        current_strength = strength_entry.strength or 0.0
        strength_entry.strength = max(0.0, current_strength - 0.1)

    db.commit()

    feedback = "Bonne réponse ! Continue comme ça." if is_correct else "Ce n'est pas tout à fait ça. Essaie de revoir la leçon."
    return {"is_correct": is_correct, "feedback": feedback}