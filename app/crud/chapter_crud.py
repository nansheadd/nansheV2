# Fichier: backend/app/crud/chapter_crud.py (VERSION FINALE CORRIGÉE)
import logging
from sqlalchemy.orm import Session, joinedload
from app.models import chapter_model, knowledge_component_model, level_model
from app.core.ai_service import generate_lesson_for_chapter, generate_exercises_for_lesson

logger = logging.getLogger(__name__)

def get_chapter_details(db: Session, chapter_id: int):
    """
    Récupère les détails d'un chapitre et ses composants de manière simple
    pour éviter les problèmes de sous-requêtes complexes avec LIMIT.
    """
    # ÉTAPE 1: On récupère JUSTE le chapitre et ses composants directs.
    # On évite les `joinedload` complexes qui causent l'erreur.
    return db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.knowledge_components),
        joinedload(chapter_model.Chapter.level) # On garde celui-ci pour le lien retour
    ).filter(
        chapter_model.Chapter.id == chapter_id
    ).first()

# --- Les tâches de fond ne changent pas ---

def generate_lesson_task(db: Session, chapter_id: int):
    """
    Tâche de fond pour générer le contenu d'une leçon pour un chapitre.
    """
    logger.info(f"Tâche de fond : Démarrage de la génération de la leçon pour le chapitre {chapter_id}")
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