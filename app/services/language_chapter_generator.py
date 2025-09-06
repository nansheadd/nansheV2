# Fichier : app/services/language_chapter_generator.py
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models.course import knowledge_graph_model
from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect as sqlalchemy_inspect

from app.models.course import chapter_model, vocabulary_item_model, grammar_rule_model
from app.models.course.knowledge_component_model import KnowledgeComponent 

from app.models.analytics.vector_store_model import VectorStore
from app.models.user.user_model import User 
from app.core.ai_service import get_text_embedding
from app.crud.course import chapter_crud 
from app.core import ai_service


logger = logging.getLogger(__name__)

# --- Aliases possibles pour "prononciation / romanisation" (agnostique langue)
_PRON_KEYS = (
    "pronunciation", "romanization", "transliteration", "reading",
    "ipa", "pinyin", "romaji", "jyutping", "wylie", "buckwalter",
    "phonetic", "phonetics", "pron"
)

def _find_similar_examples(db: Session, topic: str, language: str, content_type: str, limit: int = 3) -> str:
    """
    Cherche des exemples similaires dans la base vectorielle et les formate pour un prompt.
    """
    try:
        # 1. Vectoriser le sujet de la recherche
        topic_embedding = ai_service.get_text_embedding(topic)
        
        # 2. Exécuter la recherche par similarité dans la base de données
        similar_examples = db.scalars(
            select(VectorStore)
            .filter(VectorStore.source_language == language)
            .filter(VectorStore.content_type == content_type)
            .order_by(VectorStore.embedding.l2_distance(topic_embedding))
            .limit(limit)
        ).all()
        
        if not similar_examples:
            logger.info(f"Aucun exemple trouvé dans la base vectorielle pour le sujet '{topic}'.")
            return ""

        # 3. Formater les exemples pour les injecter dans le prompt de l'IA
        context = "Voici quelques exemples de haute qualité pour t'inspirer. Suis leur style, leur ton et leur structure :\n\n"
        for i, ex in enumerate(similar_examples):
            context += f"--- EXEMPLE {i+1} ---\n{ex.chunk_text}\n\n"
        
        logger.info(f"{len(similar_examples)} exemples pertinents ont été trouvés pour le sujet '{topic}'.")
        return context
    except Exception as e:
        logger.error(f"Erreur lors de la recherche d'exemples similaires pour '{topic}': {e}")
        return ""
    

def _index_lesson_content(db: Session, chapter_id: int, lesson_text: str):
    """Chunks a lesson into paragraphs and indexes them in the vector store."""
    if not lesson_text:
        return

    # Simple chunking by splitting on double newlines
    chunks = re.split(r'\n\s*\n', lesson_text)
    
    for chunk in chunks:
        chunk = chunk.strip()
        # We ignore small chunks that are likely just titles or noise
        if len(chunk) < 50: 
            continue
            
        # Create the embedding for the chunk
        embedding = get_text_embedding(chunk)
        
        # Save the chunk and its embedding to the database
        vector_entry = VectorStore(
            chapter_id=chapter_id,
            chunk_text=chunk,
            embedding=embedding
        )
        db.add(vector_entry)
    
    db.commit()
    logger.info(f"✅ Indexed {len(chunks)} chunks for chapter {chapter_id}.")

# Now, find where a lesson is saved (e.g., in `generate_chapter_content_pipeline`)
# and call this function immediately after.
#
# EXAMPLE:
#   chapter.lesson_text = dialogue_text
#   chapter.lesson_status = "completed"
#   db.commit() # Commit the lesson text first
#   _index_lesson_content(db, chapter.id, dialogue_text)

def _update_chapter_progress(db: Session, chapter: chapter_model.Chapter, step: str, progress: int):
    """Met à jour la progression de la génération pour un chapitre."""
    db_chapter = db.get(chapter_model.Chapter, chapter.id)
    if db_chapter:
        db_chapter.generation_step = step
        db_chapter.generation_progress = progress
        db.commit()
        logger.info(f"  -> Progress Update (Chapter ID {chapter.id}): {progress}% - {step}")
        time.sleep(0.5) # Laisse le temps au frontend de rafraîchir


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

def generate_chapter_content_pipeline(db: Session, chapter: chapter_model.Chapter, user: User):
    """
    Pipeline JIT qui génère le contenu d'un chapitre en utilisant le RAG
    pour améliorer la vitesse et la qualité, tout en gérant les chapitres
    théoriques et pratiques.
    """
    try:
        logger.info(f"Pipeline JIT (Langue) : Démarrage pour le chapitre '{chapter.title}'")
        _update_chapter_progress(db, chapter, "Analyse du chapitre...", 5)
        course = chapter.level.course
        course_language = course.title.replace("apprendre le ", "").strip().lower()

        # --- AIGUILLAGE : CHAPITRE THÉORIQUE OU PRATIQUE ? ---
        if chapter.is_theoretical:
            # --- PIPELINE POUR CHAPITRE THÉORIQUE (Introduction, etc.) ---
            # Le RAG est moins crucial ici car le sujet est très spécifique.
            logger.info(f"Chapitre théorique détecté pour '{chapter.title}'.")
            
            _update_chapter_progress(db, chapter, "Rédaction de la leçon théorique...", 20)
            lesson_text = ai_service.generate_writing_system_lesson(
                course_title=course.title,
                chapter_title=chapter.title,
                model_choice=course.model_choice
            )
            chapter.lesson_text = lesson_text
            chapter.lesson_status = "completed"
            _update_chapter_progress(db, chapter, "Leçon terminée.", 70)

            chapter.exercises_status = "completed" # Pas d'exercices pour les chapitres théoriques
            _update_chapter_progress(db, chapter, "Finalisation...", 100)

        else:
            # --- PIPELINE AMÉLIORÉE AVEC RAG POUR CHAPITRE PRATIQUE ---
            logger.info(f"Chapitre pratique détecté. Activation du RAG pour '{chapter.title}'.")
            
            # 1. RÉCUPÉRATION (Retrieval)
            _update_chapter_progress(db, chapter, "Recherche d'exemples pertinents...", 10)
            chapter_topic = f"Leçon sur : {chapter.title}"
            # On cherche des exemples pour chaque type de contenu dont nous avons besoin
            grammar_context = _find_similar_examples(db, chapter_topic, course_language, "grammar_rule", limit=3)
            vocab_context = _find_similar_examples(db, chapter_topic, course_language, "vocabulary_set", limit=2)
            rag_context = grammar_context + vocab_context

            # 2. GÉNÉRATION AUGMENTÉE (Augmented Generation) - Vocabulaire et Grammaire
            _update_chapter_progress(db, chapter, "Génération du vocabulaire et de la grammaire...", 20)
            pedagogical_content = ai_service.generate_language_pedagogical_content(
                course_title=course.title, 
                chapter_title=chapter.title, 
                model_choice=course.model_choice,
                rag_context=rag_context # Injection de nos exemples !
            )
            vocab_items = _save_vocabulary(db, chapter.id, pedagogical_content.get("vocabulary", []))
            grammar_rules = _save_grammar(db, chapter.id, pedagogical_content.get("grammar", []))

            # 3. GÉNÉRATION AUGMENTÉE - Dialogue
            _update_chapter_progress(db, chapter, "Création d'un dialogue contextuel...", 50)
            dialogue_context = _find_similar_examples(db, chapter_topic, course_language, "dialogue", limit=3)
            dialogue_text = ai_service.generate_language_dialogue(
                course_title=course.title, chapter_title=chapter.title, vocabulary=vocab_items,
                grammar=grammar_rules, model_choice=course.model_choice,
                rag_context=dialogue_context # On utilise le contexte spécifique aux dialogues
            )
            chapter.lesson_text = dialogue_text
            chapter.lesson_status = "completed"
            _update_chapter_progress(db, chapter, "Dialogue terminé.", 70)

            # 4. GÉNÉRATION AUGMENTÉE - Exercices
            _update_chapter_progress(db, chapter, "Préparation des exercices sur mesure...", 80)
            exercise_context = _find_similar_examples(db, chapter_topic, course_language, "exercise", limit=4)
            system_prompt_exercises = ai_service.prompt_manager.get_prompt(
                "generic_content.exercises_rag", # On utilise un prompt qui accepte le RAG
                course_type='langue',
                chapter_title=chapter.title,
                lesson_content=dialogue_text,
                rag_context=exercise_context, # Injection des exemples d'exercices
                ensure_json=True
            )
            exercises_data = ai_service.call_ai_and_log(
                db=db, user=user, model_choice=course.model_choice,
                system_prompt=system_prompt_exercises, user_prompt="Génère les exercices en te basant sur la leçon et les exemples fournis.",
                feature_name="exercise_generation_rag_lang"
            ).get("exercises", [])
            
            _save_exercises_data(db, chapter, exercises_data)
            chapter.exercises_status = "completed"
            _update_chapter_progress(db, chapter, "Finalisation...", 100)

        db.commit()
        logger.info(f"Pipeline JIT (Langue) : SUCCÈS pour le chapitre {chapter.id}")

    except Exception as e:
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

def _save_vocabulary(db: Session, chapter_id: int, vocabulary_data: List[Dict[str, Any]]) -> List[vocabulary_item_model.VocabularyItem]:
    """
    Sauvegarde le vocabulaire généré en base de données de manière robuste.
    """
    logger.info(f"      -> Sauvegarde de {len(vocabulary_data)} éléments de vocabulaire...")
    created_items = []
    for item_data in vocabulary_data:
        if not isinstance(item_data, dict):
            logger.warning(f"Élément de vocabulaire invalide ignoré (n'est pas un dictionnaire): {item_data}")
            continue

        # V-- LA CORRECTION EST ICI --V
        # On cherche le mot de vocabulaire sous plusieurs clés possibles.
        word = item_data.get("word") or item_data.get("term") or item_data.get("expression")

        # Si aucun mot n'est trouvé, on ignore cet élément pour éviter une erreur.
        if not word:
            logger.warning(f"Élément de vocabulaire invalide ignoré (clé 'word' ou 'term' manquante): {item_data}")
            continue

        db_item = vocabulary_item_model.VocabularyItem(
            chapter_id=chapter_id,
            word=word,
            pinyin=item_data.get("pinyin") or item_data.get("pronunciation"),
            translation=item_data.get("translation"),
            # Ajout d'un champ optionnel pour plus de richesse
            example_sentence=item_data.get("example_sentence") 
        )
        db.add(db_item)
        created_items.append(db_item)
    
    # On déplace le commit à l'extérieur de la boucle pour de meilleures performances
    if created_items:
        db.commit()
        for item in created_items:
            db.refresh(item)
            
    return created_items

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
        logger.warning(f"La génération des exercices pour le chapitre {chapter.id} n'a retourné aucun exercice.")
        return

    for data in exercises_data:
        # --- LA CORRECTION EST ICI ---
        # On s'assure que la catégorie a TOUJOURS une valeur.
        category = data.get("category") or chapter.title
        # -------------------------

        component = KnowledgeComponent(
            chapter_id=chapter.id,
            title=data.get("title", "Exercice sans titre"),
            category=category, # On utilise notre variable sécurisée
            component_type=data.get("component_type", "unknown"),
            bloom_level=data.get("bloom_level", "remember"),
            content_json=data.get("content_json", {})
        )
        db.add(component)
    db.commit()
