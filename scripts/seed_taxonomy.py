import argparse
import json
import logging
import torch
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

# --- Configuration Générale ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MODEL_NAME = 'all-MiniLM-L6-v2'

# --- Fichiers de Données ---
TAXONOMY_FILEPATH = "app/data/taxonomy_definitions.json"
JAPANESE_PLAN_FILEPATH = "app/data/japanese_course_plan.json"
JAPANESE_COURSE_SKILL = "japonais"


def get_embedding_model():
    """Charge et retourne le modèle SentenceTransformer en détectant le matériel disponible."""
    if torch.cuda.is_available():
        device = 'cuda'
    elif torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
    logger.info(f"Chargement du modèle '{MODEL_NAME}' sur le device : '{device}'...")
    return SentenceTransformer(MODEL_NAME, device=device)


def seed_taxonomy_definitions(db: Session, model):
    """Peuple la base vectorielle avec les définitions de la taxonomie."""
    logger.info("--- Début du seeding des définitions de la taxonomie ---")
    try:
        with open(TAXONOMY_FILEPATH, 'r', encoding='utf-8') as f:
            taxonomy_items = json.load(f)
    except Exception as e:
        logger.error(f"Erreur de lecture du fichier '{TAXONOMY_FILEPATH}': {e}")
        return

    # Nettoyage des anciennes entrées
    num_deleted = db.query(VectorStore).filter(VectorStore.content_type == 'taxonomy_definition').delete()
    db.commit()
    logger.info(f"{num_deleted} anciennes définitions de taxonomie ont été supprimées.")

    entries_to_add = []
    for item in taxonomy_items:
        # --- LA CORRECTION EST ICI ---
        # On vérifie que 'item' est bien un dictionnaire avant de continuer
        if not isinstance(item, dict):
            logger.warning(f"Élément ignoré dans la taxonomie car il n'est pas un objet valide : {item}")
            continue # On passe à l'élément suivant
        # ---------------------------

        definitions = item.get("definitions", [])
        if not definitions: continue

        # On s'assure que les clés nécessaires existent
        domain = item.get("domain")
        area = item.get("area")
        skill = item.get("skill")

        if not all([domain, area, skill]):
            logger.warning(f"Élément ignoré car il manque une clé (domain, area, ou skill): {item}")
            continue

        embeddings = model.encode(definitions, show_progress_bar=False)
        for i, definition_text in enumerate(definitions):
            entries_to_add.append(VectorStore(
                chunk_text=definition_text, embedding=embeddings[i], domain=domain,
                area=area, skill=skill, content_type="taxonomy_definition"
            ))

    if entries_to_add:
        db.add_all(entries_to_add)
        db.commit()
        logger.info(f"✅ SUCCÈS : {len(entries_to_add)} définitions de taxonomie ajoutées.")


def seed_japanese_course_plan(db: Session, model):
    """Peuple la base vectorielle avec le plan de cours de référence pour le japonais."""
    logger.info(f"--- Début du seeding du plan de cours '{JAPANESE_COURSE_SKILL}' ---")
    try:
        with open(JAPANESE_PLAN_FILEPATH, 'r', encoding='utf-8') as f:
            plan_json = json.load(f)
    except Exception as e:
        logger.error(f"Erreur de lecture du fichier '{JAPANESE_PLAN_FILEPATH}': {e}")
        return

    plan_text = json.dumps(plan_json, indent=2, ensure_ascii=False)
    embedding = model.encode(plan_text)

    # Nettoyage de l'ancienne entrée
    db.query(VectorStore).filter(VectorStore.content_type == 'course_plan', VectorStore.skill == JAPANESE_COURSE_SKILL).delete()
    db.commit()

    # Ajout de la nouvelle entrée
    db.add(VectorStore(
        chunk_text=plan_text,
        embedding=embedding,
        domain="langues",
        area="japonais",  # L'étiquette 'area' est maintenant le nom de la langue
        skill=JAPANESE_COURSE_SKILL,
        content_type="course_plan"
    ))
    db.commit()
    logger.info(f"✅ SUCCÈS : Le plan de cours pour '{JAPANESE_COURSE_SKILL}' a été ajouté.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Peupler la base de données vectorielle.")
    parser.add_argument(
        'type',
        choices=['taxonomy', 'plan', 'all'],
        help="Le type de données à peupler : 'taxonomy' (définitions), 'plan' (cours de japonais), ou 'all' (les deux)."
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.commit()

        model = get_embedding_model()

        if args.type in ['taxonomy', 'all']:
            seed_taxonomy_definitions(db, model)
        
        if args.type in ['plan', 'all']:
            seed_japanese_course_plan(db, model)
            
        logger.info("Toutes les opérations de seeding demandées sont terminées.")
    except Exception as e:
        logger.error(f"Une erreur est survenue durant le processus de seeding: {e}", exc_info=True)
    finally:
        db.close()