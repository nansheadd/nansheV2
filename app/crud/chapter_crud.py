# Fichier: backend/app/crud/chapter_crud.py
from sqlalchemy.orm import Session, joinedload
from app.models import chapter_model, knowledge_component_model
from app.core.ai_service import generate_lesson_for_chapter, generate_exercises_for_lesson
import logging

logger = logging.getLogger(__name__)

def get_chapter_details(db: Session, chapter_id: int):
    """
    Récupère les détails d'un chapitre, incluant sa leçon et ses exercices.
    Génère le contenu à la volée si nécessaire.
    """
    # On récupère le chapitre et on pré-charge ses exercices
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.knowledge_components)
    ).filter_by(id=chapter_id).first()

    if not chapter:
        return None

    # Étape 1 : Générer la leçon si elle n'existe pas
    if not chapter.is_lesson_generated:
        logger.info(f"Leçon non trouvée pour '{chapter.title}'. Génération IA...")
        lesson_text = generate_lesson_for_chapter(chapter.title)
        if lesson_text:
            chapter.lesson_text = lesson_text
            chapter.is_lesson_generated = True
            db.add(chapter)
            db.commit()
            db.refresh(chapter)
            logger.info(f"Leçon générée pour '{chapter.title}'.")

    # Étape 2 : Générer les exercices si ils n'existent pas
    if not chapter.are_exercises_generated and chapter.lesson_text:
        logger.info(f"Exercices non trouvés pour '{chapter.title}'. Génération IA...")
        exercises_data = generate_exercises_for_lesson(chapter.lesson_text, chapter.title)

        for data in exercises_data:
            if "error" not in data:
                component = knowledge_component_model.KnowledgeComponent(
                    chapter_id=chapter.id,
                    title=data.get("title"),
                    category=data.get("category"),
                    component_type=data.get("component_type"),
                    bloom_level=data.get("bloom_level"),
                    content_json=data.get("content_json")
                )
                db.add(component)

        chapter.are_exercises_generated = True
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
        logger.info(f"Exercices générés pour '{chapter.title}'.")

    return chapter