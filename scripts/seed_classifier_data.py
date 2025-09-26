# Fichier: backend/scripts/seed_classifier_data.py (ADAPTÉ À LA NOMENCLATURE)

import json
import logging
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# --- Configuration du chemin et des imports ---
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore
from app.services.rag_utils import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRAINING_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "training_data.jsonl"

def seed_classifier_from_jsonl(skip_embeddings: bool = False):
    db: Session = SessionLocal()
    try:
        logger.info("--- Démarrage du seeding pour le classifieur depuis le fichier .jsonl ---")
        if not TRAINING_FILE.exists():
            logger.error(f"❌ Fichier d'entraînement non trouvé : {TRAINING_FILE}")
            return
        logger.info(f"✅ Fichier d'entraînement trouvé : {TRAINING_FILE.name}")

        num_deleted = db.query(VectorStore).delete()
        if num_deleted > 0:
            db.commit()
            logger.warning(f"🧹 {num_deleted} anciennes entrées ont été supprimées de la VectorStore.")

        if skip_embeddings:
            logger.info("ℹ️ Les embeddings ne seront pas générés (mode texte brut activé).")

        vectors_to_add = []
        count = 0
        with open(TRAINING_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    text = data.get("text")
                    
                    # --- LA CORRECTION EST ICI ---
                    # On respecte votre nomenclature en priorisant "main_skill",
                    # puis en se rabattant sur "label" si "main_skill" n'existe pas.
                    main_skill = data.get("main_skill") or data.get("label")
                    
                    if not text or not main_skill:
                        logger.warning(f"Ligne ignorée (text ou main_skill/label manquant): {line.strip()}")
                        continue

                    # On récupère domain et area s'ils existent, sinon on met des valeurs par défaut.
                    domain = data.get("domain", "unknown")
                    area = data.get("area", "unknown")

                    logger.info(f"  -> Traitement : '{text}' -> Skill: '{main_skill}' (Domain: {domain})")
                    
                    embedding = None if skip_embeddings else get_embedding(text)

                    new_vector = VectorStore(
                        chunk_text=text,
                        embedding=embedding,
                        domain=domain,
                        area=area,
                        skill=main_skill  # On stocke la valeur trouvée dans la colonne "skill"
                    )
                    vectors_to_add.append(new_vector)
                    count += 1
                except json.JSONDecodeError:
                    logger.warning(f"Ligne JSON malformée ignorée : {line.strip()}")

        if vectors_to_add:
            db.add_all(vectors_to_add)
            db.commit()
            logger.info(f"✅ SUCCÈS : {count} exemples d'entraînement ont été vectorisés et ajoutés.")
        else:
            logger.info("ℹ️ Aucun exemple d'entraînement valide trouvé.")

    except Exception as e:
        logger.error(f"❌ Une erreur critique est survenue : {e}", exc_info=True)
        db.rollback()
    finally:
        logger.info("--- Fin du seeding. Fermeture de la session DB. ---")
        db.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed du classifieur depuis training_data.jsonl")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Ne calcule pas les embeddings et stocke uniquement le texte brut.",
    )

    args = parser.parse_args()
    seed_classifier_from_jsonl(skip_embeddings=args.skip_embeddings)
