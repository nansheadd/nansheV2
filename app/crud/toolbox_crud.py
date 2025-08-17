# Fichier: backend/app/crud/toolbox_crud.py (MODIFIÉ)
import json
from sqlalchemy.orm import Session, joinedload
from app.models.user.user_model import User
# Ajout des imports manquants
from app.models.course import course_model, chapter_model, knowledge_component_model, vocabulary_item_model, grammar_rule_model
from app.models.progress import user_answer_log_model, user_topic_performance_model
from app.core import ai_service

def ask_coach(db: Session, user: User, message: str, context: dict, history: list) -> str:
    # ... (la récupération des données de base reste la même)
    course_id = context.get('courseId')
    chapter_id = context.get('chapterId')
    course = db.get(course_model.Course, course_id) if course_id else None
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.vocabulary_items),
        joinedload(chapter_model.Chapter.grammar_rules)
    ).filter_by(id=chapter_id).first() if chapter_id else None
    weak_topics_query = db.query(user_topic_performance_model.UserTopicPerformance).filter_by(user_id=user.id, course_id=course_id).order_by(user_topic_performance_model.UserTopicPerformance.mastery_score.asc()).limit(3).all() if course_id else []
    recent_errors_query = db.query(user_answer_log_model.UserAnswerLog).join(knowledge_component_model.KnowledgeComponent).join(chapter_model.Chapter).join(course_model.Level).filter(user_answer_log_model.UserAnswerLog.user_id == user.id, course_model.Level.course_id == course_id, user_answer_log_model.UserAnswerLog.status == 'incorrect').order_by(user_answer_log_model.UserAnswerLog.answered_at.desc()).limit(5).all() if course_id else []

    # --- NOUVELLE LOGIQUE DE CONDENSATION ---
    
    # 1. Condenser l'historique si la conversation est longue
    history_for_prompt = json.dumps(history, ensure_ascii=False)
    if len(history) > 6: # Seuil arbitraire, 6 tours = 3 questions/réponses
        history_text = "\n".join([f"{msg['author']}: {msg['message']}" for msg in history])
        history_for_prompt = ai_service._summarize_text_for_prompt(
            db=db,
            user=user,
            text_to_summarize=history_text,
            prompt_name="toolbox.summarize_history"
        )

    # 2. Condenser les erreurs si elles sont nombreuses
    recent_errors_list = [f"- Exercice '{e.knowledge_component.title}': réponse '{e.user_answer_json}'" for e in recent_errors_query]
    errors_for_prompt = json.dumps(recent_errors_list, ensure_ascii=False)
    if len(recent_errors_list) > 2:
        errors_text = "\n".join(recent_errors_list)
        errors_for_prompt = ai_service._summarize_text_for_prompt(
            db=db,
            user=user,
            text_to_summarize=errors_text,
            prompt_name="toolbox.summarize_errors"
        )
        
    # Le reste de la préparation des données
    weak_topics = [f"{wt.topic_category} (Maîtrise: {wt.mastery_score:.0%})" for wt in weak_topics_query]
    vocab_for_prompt = [{"term": v.term, "translation": v.translation} for v in (chapter.vocabulary_items if chapter else [])]
    grammar_for_prompt = [{"rule": g.rule_name, "explanation": g.explanation} for g in (chapter.grammar_rules if chapter else [])]
    # --- FIN DE LA LOGIQUE DE CONDENSATION ---

    system_prompt = ai_service.prompt_manager.get_prompt(
        "toolbox.coach_tutor",
        context=context,
        course=course,
        chapter=chapter,
        weak_topics=json.dumps(weak_topics, ensure_ascii=False),
        # On utilise nos variables condensées
        recent_errors=errors_for_prompt,
        history=history_for_prompt,
        chapter_vocabulary=json.dumps(vocab_for_prompt, ensure_ascii=False),
        chapter_grammar=json.dumps(grammar_for_prompt, ensure_ascii=False),
        user_message=message,
        ensure_json=True
    )
    
    # L'appel final utilise maintenant notre wrapper de logging
    response_data = ai_service.call_ai_and_log(
        db=db,
        user=user,
        model_choice="openai_gpt4o-mini",
        system_prompt=system_prompt,
        user_prompt="Réponds à la question de l'utilisateur en te basant sur le contexte.",
        feature_name="coach_ia"
    )

    return response_data.get("response", "Désolé, je rencontre une difficulté pour répondre.")
