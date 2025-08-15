# Fichier à créer : nanshe/backend/app/services/language_chapter_generator.py

import logging
import json
from sqlalchemy.orm import Session
from app.models.course import chapter_model, vocabulary_item_model, grammar_rule_model, knowledge_component_model
from app.core import ai_service

# On utilise les nouveaux chemins d'importation
from app.models.course import chapter_model, vocabulary_item_model, grammar_rule_model
from app.core import ai_service
from app.crud.course import chapter_crud # Pour réutiliser la sauvegarde des exercices

logger = logging.getLogger(__name__)

def generate_chapter_content_pipeline(db: Session, chapter: chapter_model.Chapter):
    """
    Pipeline JIT complète pour générer tout le contenu d'un chapitre de langue.
    """
    try:
        logger.info(f"Pipeline JIT (Langue) : Démarrage pour le chapitre '{chapter.title}'")
        course = chapter.level.course
        
        # ÉTAPE 1: Vocabulaire & Grammaire
        pedagogical_content = ai_service.generate_language_pedagogical_content(
            course_title=course.title, chapter_title=chapter.title, model_choice=course.model_choice
        )
        vocab_items = _save_vocabulary(db, chapter.id, pedagogical_content.get("vocabulary", []))
        grammar_rules = _save_grammar(db, chapter.id, pedagogical_content.get("grammar", []))
        logger.info(f"  -> Étape 1/3 : Vocabulaire et grammaire générés.")

        # ÉTAPE 2: Dialogue Contextuel
        dialogue_text = ai_service.generate_language_dialogue(
            course_title=course.title, chapter_title=chapter.title, vocabulary=vocab_items, grammar=grammar_rules, model_choice=course.model_choice
        )
        chapter.lesson_text = dialogue_text
        chapter.lesson_status = "completed"
        logger.info(f"  -> Étape 2/3 : Dialogue contextuel généré.")

        # ÉTAPE 3: Exercices Ciblés
        exercises_data = ai_service.generate_exercises_for_lesson(
            lesson_text=dialogue_text, chapter_title=chapter.title, course_type='langue', model_choice=course.model_choice
        )
        _save_exercises_data(db, chapter, exercises_data) # On utilise la fonction locale
        chapter.exercises_status = "completed"
        logger.info(f"  -> Étape 3/3 : Exercices ciblés générés.")
        
        db.commit()
        logger.info(f"Pipeline JIT (Langue) : SUCCÈS pour le chapitre {chapter.id}")

    except Exception as e:
        logger.error(f"Pipeline JIT (Langue) : ÉCHEC pour le chapitre {chapter.id}. Erreur: {e}", exc_info=True)
        db.rollback()
        chapter_to_fail = db.get(chapter_model.Chapter, chapter.id)
        if chapter_to_fail:
            chapter_to_fail.lesson_status = "failed"
            chapter_to_fail.exercises_status = "failed"
            db.commit()

# --- Fonctions d'aide pour la sauvegarde en BDD ---

def _save_vocabulary(db: Session, chapter_id: int, vocab_data: list) -> list:
    items = []
    for item_data in vocab_data:
        db_item = vocabulary_item_model.VocabularyItem(chapter_id=chapter_id, **item_data)
        db.add(db_item)
        items.append(item_data)
    db.commit()
    return items

def _save_grammar(db: Session, chapter_id: int, grammar_data: list) -> list:
    rules = []
    for rule_data in grammar_data:
        db_rule = grammar_rule_model.GrammarRule(chapter_id=chapter_id, **rule_data)
        db.add(db_rule)
        rules.append(rule_data)
    db.commit()
    return rules

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