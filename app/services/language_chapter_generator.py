# Fichier à créer : nanshe/backend/app/services/language_chapter_generator.py

import logging
import json
from sqlalchemy.orm import Session
from app.models import chapter_model, vocabulary_item_model, grammar_rule_model
from app.core import ai_service
from typing import Dict, Any

logger = logging.getLogger(__name__)

def _generate_pedagogical_content(db: Session, chapter: chapter_model.Chapter):
    """
    Pipeline JIT pour générer tout le contenu d'un chapitre de langue :
    vocabulaire, grammaire, dialogue et exercices ciblés.
    """
    try:
        logger.info(f"Pipeline JIT (Langue) : Démarrage pour le chapitre '{chapter.title}'")
        # --- MODIFICATION CLÉ : On récupère le contexte global ---
        course = chapter.level.course
        course_title = course.title
        model_choice = course.model_choice
        # ---------------------------------------------------------
        
        # --- ÉTAPE 1: Générer le contenu pédagogique de base ---
        logger.info("  Étape 1a: Génération du vocabulaire et de la grammaire.")
        pedagogical_content = ai_service.generate_language_pedagogical_content(
            course_title=course_title, # <-- On passe le contexte
            chapter_title=chapter.title,
            model_choice=model_choice
        )
        
        vocab_items = _save_vocabulary(db, chapter.id, pedagogical_content.get("vocabulary", []))
        grammar_rules = _save_grammar(db, chapter.id, pedagogical_content.get("grammar", []))
        logger.info("  Étape 1b: Vocabulaire et grammaire sauvegardés.")

        # --- ÉTAPE 2: Générer un dialogue contextuel ---
        logger.info("  Étape 2a: Génération du dialogue.")
        dialogue_text = ai_service.generate_language_dialogue(
            course_title=course_title, # <-- On passe le contexte
            chapter_title=chapter.title,
            vocabulary=vocab_items,
            grammar=grammar_rules,
            model_choice=model_choice
        )
        chapter.lesson_text = dialogue_text
        chapter.lesson_status = "completed"
        logger.info("  Étape 2b: Dialogue généré et sauvegardé.")

        # --- ÉTAPE 3: Générer des exercices ciblés ---
        logger.info("  Étape 3a: Génération des exercices ciblés.")
        exercises_data = ai_service.generate_exercises_for_lesson(
            lesson_text=dialogue_text,
            chapter_title=chapter.title,
            course_type='langue',
            model_choice=model_choice
        )
        
        from app.crud.chapter_crud import _save_exercises_data
        _save_exercises_data(db, chapter, exercises_data)
        chapter.exercises_status = "completed"
        logger.info("  Étape 3b: Exercices générés et sauvegardés.")
        
        db.commit()
        logger.info(f"Pipeline JIT (Langue) : Contenu complet généré pour le chapitre {chapter.id}")

    except Exception as e:
        logger.error(f"Pipeline JIT (Langue) : Échec pour le chapitre {chapter.id}. Erreur: {e}", exc_info=True)
        db.rollback()
        chapter_to_fail = db.get(chapter_model.Chapter, chapter.id)
        if chapter_to_fail:
            chapter_to_fail.lesson_status = "failed"
            chapter_to_fail.exercises_status = "failed"
            db.commit()

            
def _save_vocabulary(db: Session, chapter_id: int, vocab_data: list) -> list:
    items = []
    for item_data in vocab_data:
        db_item = vocabulary_item_model.VocabularyItem(
            chapter_id=chapter_id,
            term=item_data.get("term"),
            translation=item_data.get("translation"),
            pronunciation=item_data.get("pronunciation"),
            example_sentence=item_data.get("example_sentence")
        )
        db.add(db_item)
        items.append(item_data)
    db.commit()
    return items

def _save_grammar(db: Session, chapter_id: int, grammar_data: list) -> list:
    rules = []
    for rule_data in grammar_data:
        db_rule = grammar_rule_model.GrammarRule(
            chapter_id=chapter_id,
            rule_name=rule_data.get("rule_name"),
            explanation=rule_data.get("explanation"),
            example_sentence=rule_data.get("example_sentence")
        )
        db.add(db_rule)
        rules.append(rule_data)
    db.commit()
    return rules

# --- Logique à ajouter dans chapter_crud.py ---
# Pour éviter la duplication, on crée une fonction de sauvegarde réutilisable
def _save_exercises_data(db: Session, chapter: chapter_model.Chapter, exercises_data: list):
    from app.models import knowledge_component_model # Import local pour éviter dépendance circulaire
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