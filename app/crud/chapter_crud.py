# Fichier: backend/app/crud/chapter_crud.py (VERSION FINALE COMPLÈTE)
from sqlalchemy.orm import Session, joinedload
from app.models import chapter_model, knowledge_component_model, level_model
from app.core.ai_service import generate_lesson_for_chapter, generate_exercises_for_lesson
import logging

logger = logging.getLogger(__name__)

def generate_lesson_task(db: Session, chapter_id: int):
    """
    Tâche de fond pour générer le contenu d'une leçon pour un chapitre.
    """
    logger.info(f"Tâche de fond : Démarrage de la génération de la leçon pour le chapitre {chapter_id}")
    # On s'assure de charger les relations nécessaires pour trouver le model_choice
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.level).joinedload(level_model.Level.course)
    ).filter(chapter_model.Chapter.id == chapter_id).first()

    if not chapter:
        logger.error(f"Tâche de fond (leçon) annulée : chapitre {chapter_id} non trouvé.")
        return

    try:
        model_choice = chapter.level.course.model_choice
        lesson_text = generate_lesson_for_chapter(chapter.title, model_choice)
        
        if lesson_text:
            chapter.lesson_text = lesson_text
            chapter.lesson_status = "completed"
            logger.info(f"Leçon générée avec succès pour le chapitre {chapter_id}.")
        else:
            raise ValueError("La génération de la leçon a renvoyé un contenu vide.")
            
    except Exception as e:
        logger.error(f"Erreur dans la tâche de génération de leçon pour le chapitre {chapter_id}: {e}")
        chapter.lesson_status = "failed"
    
    db.commit()

def generate_exercises_task(db: Session, chapter_id: int):
    """
    Tâche de fond pour générer les exercices d'un chapitre.
    """
    logger.info(f"Tâche de fond : Démarrage de la génération des exercices pour le chapitre {chapter_id}")
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.level).joinedload(level_model.Level.course)
    ).filter(chapter_model.Chapter.id == chapter_id).first()

    if not chapter or not chapter.lesson_text:
        logger.error(f"Tâche de fond (exercices) annulée : chapitre {chapter_id} ou sa leçon non trouvé.")
        return

    try:
        model_choice = chapter.level.course.model_choice
        exercises_data = generate_exercises_for_lesson(chapter.lesson_text, chapter.title, model_choice)

        if not exercises_data:
            raise ValueError("La génération des exercices a renvoyé une liste vide.")

        for data in exercises_data:
            if "error" not in data:
                component = knowledge_component_model.KnowledgeComponent(
                    chapter_id=chapter.id,
                    title=data.get("title", "Exercice sans titre"),
                    category=data.get("category", "Général"),
                    component_type=data.get("component_type", "unknown"),
                    bloom_level=data.get("bloom_level", "remember"),
                    content_json=data.get("content_json", {})
                )
                db.add(component)
        
        chapter.exercises_status = "completed"
        logger.info(f"Exercices générés avec succès pour le chapitre {chapter_id}.")

    except Exception as e:
        logger.error(f"Erreur dans la tâche de génération d'exercices pour le chapitre {chapter_id}: {e}")
        chapter.exercises_status = "failed"
    
    db.commit()


def get_chapter_details(db: Session, chapter_id: int):
    """
    Récupère les détails d'un chapitre, ses composants, et les réponses associées
    SANS déclencher de génération. C'est le routeur qui se chargera de la logique métier.
    """
    return db.query(chapter_model.Chapter).options(
        # On charge les composants, et pour chaque composant, on charge toutes ses réponses
        joinedload(chapter_model.Chapter.knowledge_components)
        .joinedload(knowledge_component_model.KnowledgeComponent.user_answers),
        # On charge le niveau pour avoir le level_id (pour le lien retour du frontend)
        joinedload(chapter_model.Chapter.level)
    ).filter(chapter_model.Chapter.id == chapter_id).first()