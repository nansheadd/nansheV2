# Fichier : app/services/language_chapter_generator.py

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect as sqlalchemy_inspect

from app.models.course import chapter_model, vocabulary_item_model, grammar_rule_model, knowledge_component_model
from app.core import ai_service
from app.crud.course import chapter_crud  # si besoin ailleurs

logger = logging.getLogger(__name__)

# --- Aliases possibles pour "prononciation / romanisation" (agnostique langue)
_PRON_KEYS = (
    "pronunciation", "romanization", "transliteration", "reading",
    "ipa", "pinyin", "romaji", "jyutping", "wylie", "buckwalter",
    "phonetic", "phonetics", "pron"
)

def _norm_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None

def _pick_pronunciation(src: Dict[str, Any]) -> str:
    """Retourne une chaîne non nulle pour la prononciation."""
    for k in _PRON_KEYS:
        v = src.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (list, tuple)) and v:
            first = v[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
        if isinstance(v, dict):
            for cand in ("value", "text"):
                vv = v.get(cand)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
    return ""  # NOT NULL safe

def _filter_to_model_columns(model_cls, data: dict) -> dict:
    """
    Garde uniquement les colonnes connues par le modèle.
    - Déporte 'id' non entier en metadata_json.ai_id (pour éviter collision PK int).
    - Met tous les extras dans metadata_json si la colonne existe.
    """
    mapper = sqlalchemy_inspect(model_cls)
    col_names = {c.key for c in mapper.columns}

    incoming = dict(data or {})

    # Protéger la PK si l'IA fournit un id string
    ai_id = None
    if "id" in incoming and not isinstance(incoming["id"], int):
        ai_id = incoming.pop("id")

    filtered = {k: v for k, v in incoming.items() if k in col_names}
    extra = {k: v for k, v in incoming.items() if k not in col_names}

    if ai_id is not None:
        extra["ai_id"] = ai_id

    if "metadata_json" in col_names and extra:
        existing = filtered.get("metadata_json")
        if isinstance(existing, dict):
            existing.update(extra)
            filtered["metadata_json"] = existing
        elif existing is None:
            filtered["metadata_json"] = extra
        else:
            filtered["metadata_json"] = extra

    return filtered

def _normalize_vocab_for_db(chapter_id: int, item: dict) -> dict:
    """
    Adapte un item IA vers tes colonnes usuelles : term, translation, pronunciation, example_sentence.
    """
    term = _norm_str(item.get("term") or item.get("tl") or item.get("text"))
    translation = _norm_str(item.get("translation") or item.get("translation_fr"))
    pronunciation = item.get("pronunciation")
    if not isinstance(pronunciation, str) or not pronunciation.strip():
        pronunciation = _pick_pronunciation(item)  # "" si rien (NOT NULL-friendly)

    example_sentence = _norm_str(item.get("example_sentence") or item.get("example_tl") or item.get("example"))

    payload = {
        "chapter_id": chapter_id,
        "term": term,
        "translation": translation,
        "pronunciation": pronunciation,
        "example_sentence": example_sentence,
        # tout le reste (lemma, pos, ipa, tags, etc.) partira en metadata_json via _filter_to_model_columns
        # on laisse 'id' IA dans item; _filter_to_model_columns le déplacera en metadata_json.ai_id
        **{k: v for k, v in item.items() if k not in {"term", "translation", "translation_fr", "pronunciation",
                                                       "romanization", "transliteration", "reading", "ipa",
                                                       "example_sentence", "example_tl", "example"}}
    }
    payload = _filter_to_model_columns(vocabulary_item_model.VocabularyItem, payload)

    # Éviter les None sur colonnes NOT NULL éventuelles
    if "pronunciation" in payload and payload["pronunciation"] is None:
        payload["pronunciation"] = ""
    if "term" in payload and payload["term"] is None:
        payload["term"] = ""  # si ta colonne est NOT NULL; sinon retire cette ligne

    # Ne jamais passer un 'id' restant
    payload.pop("id", None)
    return payload

def _normalize_grammar_for_db(chapter_id: int, rule: dict) -> dict:
    rule_name = _norm_str(rule.get("rule_name") or rule.get("name") or rule.get("title"))
    explanation = _norm_str(rule.get("explanation_fr") or rule.get("explanation"))

    payload = {
        "chapter_id": chapter_id,
        "rule_name": rule_name,
        "explanation": explanation,
        "patterns": rule.get("patterns"),
        "examples": rule.get("examples"),
        "common_errors_fr": rule.get("common_errors_fr") or rule.get("common_errors"),
        **{k: v for k, v in rule.items() if k not in {
            "rule_name", "name", "title", "explanation_fr", "explanation",
            "patterns", "examples", "common_errors_fr", "common_errors"
        }}
    }
    payload = _filter_to_model_columns(grammar_rule_model.GrammarRule, payload)
    payload.pop("id", None)
    return payload

def generate_chapter_content_pipeline(db: Session, chapter: chapter_model.Chapter):
    """ Pipeline JIT complète pour générer tout le contenu d'un chapitre de langue. """
    try:
        logger.info(f"Pipeline JIT (Langue) : Démarrage pour le chapitre '{chapter.title}'")
        course = chapter.level.course

        # ÉTAPE 1: Vocabulaire & Grammaire
        pedagogical_content = ai_service.generate_language_pedagogical_content(
            course_title=course.title,
            chapter_title=chapter.title,
            model_choice=course.model_choice
        )
        vocab_items = _save_vocabulary(db, chapter.id, pedagogical_content.get("vocabulary", []))
        grammar_rules = _save_grammar(db, chapter.id, pedagogical_content.get("grammar", []))
        logger.info(" -> Étape 1/3 : Vocabulaire et grammaire générés.")

        # ÉTAPE 2: Dialogue Contextuel
        dialogue_text = ai_service.generate_language_dialogue(
            course_title=course.title,
            chapter_title=chapter.title,
            vocabulary=vocab_items,   # on renvoie les items IA (ids/terms) à l'IA, pas la forme DB
            grammar=grammar_rules,
            model_choice=course.model_choice
        )
        chapter.lesson_text = dialogue_text
        chapter.lesson_status = "completed"
        logger.info(" -> Étape 2/3 : Dialogue contextuel généré.")

        # ÉTAPE 3: Exercices Ciblés
        exercises_data = ai_service.generate_exercises_for_lesson(
            lesson_text=dialogue_text,
            chapter_title=chapter.title,
            course_type='langue',
            model_choice=course.model_choice
        )
        _save_exercises_data(db, chapter, exercises_data)
        chapter.exercises_status = "completed"
        logger.info(" -> Étape 3/3 : Exercices ciblés générés.")

        db.commit()
        logger.info(f"Pipeline JIT (Langue) : SUCCÈS pour le chapitre {chapter.id}")

    except Exception as e:
        # sécurise l'accès à l'id + rollback AVANT tout autre accès DB
        chap_id = getattr(chapter, "id", None)
        logger.error(f"Pipeline JIT (Langue) : ÉCHEC pour le chapitre {chap_id}. Erreur: {e}", exc_info=True)
        db.rollback()

        if chap_id:
            chapter_to_fail = db.get(chapter_model.Chapter, chap_id)
            if chapter_to_fail:
                chapter_to_fail.lesson_status = "failed"
                chapter_to_fail.exercises_status = "failed"
                db.commit()

# --- Fonctions d'aide pour la sauvegarde en BDD ---

def _save_vocabulary(db: Session, chapter_id: int, vocab_data: list) -> list:
    items_for_ai = []
    for item_data in (vocab_data or []):
        if not isinstance(item_data, dict):
            item_data = {"term": str(item_data)}

        # Conserve la version IA pour les étapes suivantes (ids symboliques, etc.)
        items_for_ai.append(item_data)

        # Normalise pour la DB (sans 'id' IA dans la PK)
        payload = _normalize_vocab_for_db(chapter_id, item_data)
        db_item = vocabulary_item_model.VocabularyItem(**payload)
        db.add(db_item)

    db.commit()
    return items_for_ai

def _save_grammar(db: Session, chapter_id: int, grammar_data: list) -> list:
    rules_for_ai = []
    for rule_data in (grammar_data or []):
        if not isinstance(rule_data, dict):
            rule_data = {"rule_name": str(rule_data)}

        rules_for_ai.append(rule_data)

        payload = _normalize_grammar_for_db(chapter_id, rule_data)
        db_rule = grammar_rule_model.GrammarRule(**payload)
        db.add(db_rule)

    db.commit()
    return rules_for_ai

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
