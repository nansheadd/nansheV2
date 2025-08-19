import json
import logging
from sqlalchemy.orm import Session, joinedload

# Imports des modèles de l'application
from app.models.user.user_model import User
from app.models.course import course_model, chapter_model, knowledge_component_model
from app.models.progress import user_answer_log_model, user_topic_performance_model
from app.models.analytics.vector_store_model import VectorStore

# Imports des services de l'application
from app.core import ai_service

logger = logging.getLogger(__name__)

def ask_coach(db: Session, user: User, message: str, context: dict, history: list) -> str:
    """
    Orchestre la réponse du Coach IA en utilisant une approche RAG et la condensation de contexte.
    """
    course_id = context.get('courseId')
    chapter_id = context.get('chapterId')

    # --- ÉTAPE 1 : RÉCUPÉRATION DES DONNÉES BRUTES ---
    course = db.get(course_model.Course, course_id) if course_id else None
    
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.vocabulary_items),
        joinedload(chapter_model.Chapter.grammar_rules)
    ).filter_by(id=chapter_id).first() if chapter_id else None
    
    weak_topics_query = db.query(user_topic_performance_model.UserTopicPerformance)\
        .filter_by(user_id=user.id, course_id=course_id)\
        .order_by(user_topic_performance_model.UserTopicPerformance.mastery_score.asc())\
        .limit(3).all() if course_id else []
    
    recent_errors_query = db.query(user_answer_log_model.UserAnswerLog)\
        .join(knowledge_component_model.KnowledgeComponent)\
        .join(chapter_model.Chapter).join(course_model.Level)\
        .filter(user_answer_log_model.UserAnswerLog.user_id == user.id,
                course_model.Level.course_id == course_id,
                user_answer_log_model.UserAnswerLog.status == 'incorrect')\
        .order_by(user_answer_log_model.UserAnswerLog.answered_at.desc())\
        .limit(5).all() if course_id else []

    # --- ÉTAPE 2 : RÉCUPÉRATION AUGMENTÉE PAR RECHERCHE (RAG) ---
    relevant_context = "Aucun contexte spécifique n'a pu être trouvé pour cette question."
    if chapter_id and message:
        question_embedding = ai_service.get_text_embedding(message)
        
        similar_chunks = db.query(VectorStore.chunk_text)\
            .filter(VectorStore.chapter_id == chapter_id)\
            .order_by(VectorStore.embedding.l2_distance(question_embedding))\
            .limit(3).all()
        
        if similar_chunks:
            relevant_context = "\n\n---\n\n".join([chunk[0] for chunk in similar_chunks])
            logger.info(f"🔍 Contexte RAG trouvé pour la question de l'utilisateur.")

    # --- ÉTAPE 3 : CONDENSATION DU CONTEXTE VOLUMINEUX ---
    history_for_prompt = json.dumps(history, ensure_ascii=False)
    if len(history) > 6: # Si plus de 3 allers-retours
        history_text = "\n".join([f"{msg['author']}: {msg['message']}" for msg in history])
        history_for_prompt = ai_service._summarize_text_for_prompt(
            db=db, user=user, text_to_summarize=history_text, prompt_name="toolbox.summarize_history"
        )

    recent_errors_list = [f"- Exercice '{e.knowledge_component.title}': réponse '{e.user_answer_json}'" for e in recent_errors_query]
    errors_for_prompt = json.dumps(recent_errors_list, ensure_ascii=False)
    if len(recent_errors_list) > 2:
        errors_text = "\n".join(recent_errors_list)
        errors_for_prompt = ai_service._summarize_text_for_prompt(
            db=db, user=user, text_to_summarize=errors_text, prompt_name="toolbox.summarize_errors"
        )
        
    # --- ÉTAPE 4 : PRÉPARATION FINALE DU PROMPT ---
    weak_topics = [f"{wt.topic_category} (Maîtrise: {wt.mastery_score:.0%})" for wt in weak_topics_query]

    # Le prompt n'a plus besoin du vocabulaire ou de la grammaire, car le RAG s'en charge.
    
    system_prompt = ai_service.prompt_manager.get_prompt(
        "toolbox.coach_tutor_rag",
        context=context,
        course=course,
        chapter=chapter,
        weak_topics=json.dumps(weak_topics, ensure_ascii=False),
        recent_errors=errors_for_prompt,
        relevant_lesson_context=relevant_context, # On injecte le contexte ciblé
        history=history_for_prompt,
        user_message=message,
        ensure_json=True
    )
    
    # --- ÉTAPE 5 : APPEL À L'IA ET LOGGING ---
    response_data = ai_service.call_ai_and_log(
        db=db,
        user=user,
        model_choice="openai_gpt4o_mini", # On peut forcer un modèle performant pour le coach
        system_prompt=system_prompt,
        user_prompt="Réponds à la question de l'utilisateur en te basant sur le contexte.",
        feature_name="coach_ia"
    )

    return response_data.get("response", "Désolé, je rencontre une difficulté pour répondre.")