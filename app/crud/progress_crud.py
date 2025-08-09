# Fichier: backend/app/crud/progress_crud.py (VERSION FINALE CORRIGÉE)
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
from app.models import (
    user_model,
    knowledge_component_model,
    user_knowledge_strength_model,
    user_answer_log_model,
    chapter_model,
    user_course_progress_model
)
from app.schemas import progress_schema
import logging

logger = logging.getLogger(__name__)

def process_user_answer(db: Session, user: user_model.User, answer_in: progress_schema.AnswerCreate):
    """
    Traite la réponse d'un utilisateur, met à jour sa force de mémorisation et enregistre la réponse.
    """
    component = db.get(knowledge_component_model.KnowledgeComponent, answer_in.component_id)
    if not component:
        return {"is_correct": False, "feedback": "Composant de connaissance non trouvé."}

    is_correct = False
    content = component.content_json
    user_answer = answer_in.user_answer_json

    # --- Logique d'Évaluation par Type (maintenant beaucoup plus robuste) ---
    if component.component_type == "qcm":
        correct_index = content.get("correct_option_index")
        
        if correct_index is None:
            correct_answer_text = content.get("correct_answer", content.get("answer"))
            if correct_answer_text and "options" in content:
                try:
                    correct_index = content["options"].index(correct_answer_text)
                except (ValueError, AttributeError):
                    correct_index = -1
        
        is_correct = (correct_index is not None and correct_index == user_answer.get("selected_option"))

    elif component.component_type == "fill_in_the_blank":
        correct_answers = []
        # On cherche la réponse sous plusieurs noms de clés possibles
        answer_key = content.get("answer") or content.get("correct_answer")
        answers_key = content.get("answers")

        if answer_key and isinstance(answer_key, str):
            correct_answers = [answer_key.lower().strip()]
        elif answers_key and isinstance(answers_key, list):
            correct_answers = [str(ans).lower().strip() for ans in answers_key]
        
        user_answers = [str(ua).lower().strip() for ua in user_answer.get("filled_blanks", [])]

        # --- CORRECTION DE LA LOGIQUE BOOLÉENNE ---
        # On s'assure que les listes ne sont pas vides avant de les comparer.
        is_correct = bool(correct_answers and user_answers and correct_answers == user_answers)

    elif component.component_type == "reorder":
        correct_order = content.get("correct_order", content.get("items", []))
        user_order = user_answer.get("ordered_items", [])
        is_correct = (correct_order == user_order)
    
    # --- Logique d'Enregistrement et SRS ---
    answer_log = user_answer_log_model.UserAnswerLog(
        user_id=user.id,
        component_id=component.id,
        is_correct=is_correct,
        user_answer_json=answer_in.user_answer_json
    )
    db.add(answer_log)

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
        strength_entry.strength = max(0.0, current_strength - 0.1)

    db.commit()

    feedback = "Bonne réponse ! Continue comme ça." if is_correct else "Ce n'est pas tout à fait ça. Essaie de revoir la leçon."
    return {"is_correct": is_correct, "feedback": feedback}

def advance_progress(db: Session, user: user_model.User, chapter_id: int):
    # ... (cette fonction reste la même que dans ma réponse précédente)
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.knowledge_components)
        .joinedload(knowledge_component_model.KnowledgeComponent.user_answers)
    ).filter(chapter_model.Chapter.id == chapter_id).first()

    if not chapter or not chapter.knowledge_components:
        return False

    for component in chapter.knowledge_components:
        last_answer = sorted(
            [a for a in component.user_answers if a.user_id == user.id],
            key=lambda x: x.answered_at, reverse=True
        )
        if not last_answer or not last_answer[0].is_correct:
            return False

    progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user.id, course_id=chapter.level.course_id
    ).first()

    if not progress: return False

    level_chapters = sorted(chapter.level.chapters, key=lambda c: c.chapter_order)
    next_chapter_order = chapter.chapter_order + 1

    if next_chapter_order < len(level_chapters):
        progress.current_chapter_order = next_chapter_order
    else:
        progress.current_level_order += 1
        progress.current_chapter_order = 0

    db.commit()
    logger.info(f"Utilisateur {user.id} a terminé le chapitre {chapter.id} et a avancé.")
    return True