# Fichier: backend/app/crud/chapter_crud.py (VERSION FINALE CORRIGÉE)
import logging
from app.models.course import chapter_model
from app.models.course import knowledge_component_model
from sqlalchemy.orm import Session, joinedload
from app.models.course import level_model
from app.models.user.user_model import User
from app.services import language_chapter_generator
from app.core.ai_service import generate_lesson_for_chapter, generate_exercises_for_lesson
from app.models.course import chapter_model, character_model, vocabulary_item_model
from app.models.progress import user_character_strength_model, user_vocabulary_strenght_model
from typing import List



logger = logging.getLogger(__name__)

def get_chapter_details(db: Session, chapter_id: int):
    """
    Récupère les détails d'un chapitre en pré-chargeant les relations imbriquées.
    """
    return db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.knowledge_components),
        # --- LIGNE MODIFIÉE ---
        # On charge le niveau, ET le cours associé à ce niveau.
        joinedload(chapter_model.Chapter.level).joinedload(level_model.Level.course)
    ).filter(
        chapter_model.Chapter.id == chapter_id
    ).first()

# --- Les tâches de fond ne changent pas ---

def generate_language_chapter_content_task(db: Session, chapter_id: int, user_id: int):
    """
    Tâche de fond qui orchestre la génération complète du contenu d'un chapitre de langue.
    """
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.level).joinedload(level_model.Level.course)
    ).filter(chapter_model.Chapter.id == chapter_id).first()
    
    user = db.get(User, user_id) # On récupère l'objet utilisateur complet

    if not chapter or not user:
        logger.error(f"Pipeline JIT annulée : chapitre {chapter_id} ou utilisateur {user_id} non trouvé.")
        return
    
    # On passe maintenant l'objet utilisateur complet à la pipeline
    language_chapter_generator.generate_chapter_content_pipeline(db, chapter, user)
# -----------------------------------------------------------------
    
    
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


def generate_exercises_task(db: Session, chapter_id: int, user_id: int): # <-- Ajouter user_id
    """
    Tâche de fond pour générer les exercices d'un chapitre.
    """
    logger.info(f"Tâche de fond : Démarrage de la génération des exercices pour le chapitre {chapter_id}")
    
    chapter = db.query(chapter_model.Chapter).options(
        joinedload(chapter_model.Chapter.level).joinedload(level_model.Level.course)
    ).filter(chapter_model.Chapter.id == chapter_id).first()
    
    user = db.get(User, user_id) # <-- Récupérer l'utilisateur

    if not chapter or not chapter.lesson_text or not user:
        logger.error(f"Tâche (exercices) annulée : chapitre {chapter_id}, sa leçon ou l'utilisateur non trouvé.")
        return

    try:
        model_choice = chapter.level.course.model_choice
        course_type = chapter.level.course.course_type
        
        # --- MODIFICATION CLÉ ---
        # On passe maintenant db et user à la fonction
        exercises_data = generate_exercises_for_lesson(
            db=db,
            user=user,
            lesson_text=chapter.lesson_text, 
            chapter_title=chapter.title, 
            course_type=course_type,
            model_choice=model_choice
        )
        # --- FIN DE LA MODIFICATION ---

        if not exercises_data:
            raise ValueError("La génération des exercices a renvoyé une liste vide.")

        _save_exercises_data(db, chapter, exercises_data)
        
        chapter.exercises_status = "completed"
        logger.info(f"Exercices générés avec succès pour le chapitre {chapter_id}.")

    except Exception as e:
        logger.error(f"Erreur dans la tâche de génération d'exercices pour le chapitre {chapter_id}: {e}")
        chapter.exercises_status = "failed"
    
    db.commit()


def generate_generic_chapter_content_task(db: Session, chapter_id: int, user_id: int):
    """
    Tâche de fond pour générer la leçon et les exercices d'un chapitre générique.
    """
    try:
        chapter = db.get(chapter_model.Chapter, chapter_id)
        if not chapter:
            logger.error(f"[JIT Task] Chapitre {chapter_id} non trouvé.")
            return

        # 1. Générer la leçon
        logger.info(f"[JIT Task] Génération de la leçon pour le chapitre '{chapter.title}'.")
        lesson_text = generate_lesson_for_chapter(
            chapter_title=chapter.title,
            model_choice=chapter.level.course.model_choice
        )
        if not lesson_text:
            raise ValueError("La génération de la leçon a échoué (contenu vide).")
        
        chapter.lesson_text = lesson_text
        chapter.lesson_status = "completed"
        db.commit()

        # 2. Générer les exercices basés sur la leçon
        logger.info(f"[JIT Task] Génération des exercices pour le chapitre '{chapter.title}'.")
        exercises_data = generate_exercises_for_lesson(
            lesson_text=chapter.lesson_text,
            chapter_title=chapter.title,
            model_choice=chapter.level.course.model_choice
        )
        if not exercises_data:
            raise ValueError("La génération des exercices a échoué.")

        for data in exercises_data:
            component = knowledge_component_model.KnowledgeComponent(
                chapter_id=chapter.id,
                title=data.get("title", "Exercice"),
                component_type=data.get("component_type", "unknown"),
                content_json=data.get("content_json", {})
            )
            db.add(component)
        
        chapter.exercises_status = "completed"
        db.commit()

        logger.info(f"[JIT Task] Contenu généré avec succès pour le chapitre {chapter_id}")

    except Exception as e:
        logger.error(f"[JIT Task] Échec pour le chapitre {chapter_id}. Erreur: {e}", exc_info=True)
        db.rollback()
        chapter = db.get(chapter_model.Chapter, chapter_id)
        if chapter:
            chapter.lesson_status = "failed"
            chapter.exercises_status = "failed"
            db.commit()


def _save_exercises_data(db: Session, chapter: chapter_model.Chapter, exercises_data: list):
    """Sauvegarde les données des exercices générés en BDD."""
    if not exercises_data:
        raise ValueError("La génération des exercices a renvoyé une liste vide.")
    for data in exercises_data:
        component = knowledge_component_model.KnowledgeComponent(
            chapter_id=chapter.id,
            title=data.get("title", "Exercice sans titre"),
            category=data.get("category", chapter.title),
            component_type=data.get("component_type", "unknown"),
            bloom_level=data.get("bloom_level", "remember"),
            content_json=data.get("content_json", {})
        )
        db.add(component)

def get_characters_with_strength(db: Session, chapter_id: int, user_id: int) -> List[character_model.Character]:
    characters = db.query(character_model.Character).filter(character_model.Character.chapter_id == chapter_id).all()
    strengths = db.query(user_character_strength_model.UserCharacterStrength).filter(user_character_strength_model.UserCharacterStrength.user_id == user_id).all()
    strength_map = {s.character_id: s.strength for s in strengths}

    for char in characters:
        char.strength = strength_map.get(char.id, 0.0)
    return characters

def get_vocabulary_with_strength(db: Session, chapter_id: int, user_id: int) -> List[vocabulary_item_model.VocabularyItem]:
    vocabulary = db.query(vocabulary_item_model.VocabularyItem).filter(vocabulary_item_model.VocabularyItem.chapter_id == chapter_id).all()
    strengths = db.query(user_vocabulary_strenght_model.UserVocabularyStrength).filter(user_vocabulary_strenght_model.UserVocabularyStrength.user_id == user_id).all()
    strength_map = {s.vocabulary_item_id: s.strength for s in strengths}

    for item in vocabulary:
        item.strength = strength_map.get(item.id, 0.0)
    return vocabulary