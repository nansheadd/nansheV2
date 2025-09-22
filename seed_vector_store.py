# Fichier: backend/seed_vector_store.py
import json
import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore
from app.core.ai_service import get_text_embedding
from app.core.embeddings import EMBEDDING_DIMENSION
from sqlalchemy import text
from app.db.base import Base 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Le chemin vers votre fichier d'exemples
EXAMPLES_FILEPATH = "app/data/vector.json"
# La dimension des vecteurs de votre modèle.
VECTOR_DIMENSION = EMBEDDING_DIMENSION

def setup_database_extension(db: Session):
    """S'assure que l'extension pgvector est activée."""
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.commit()
        logger.info("L'extension 'vector' de PostgreSQL est activée.")
    except Exception as e:
        logger.error(f"Impossible d'activer l'extension 'vector'. Assurez-vous qu'elle est installée. Erreur: {e}")
        db.rollback()
        raise

def clear_vector_store(db: Session):
    """Vide la table vector_store pour éviter les doublons lors du re-peuplement."""
    try:
        num_deleted = db.query(VectorStore).delete()
        db.commit()
        logger.info(f"{num_deleted} entrées ont été supprimées de la base vectorielle.")
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de la base vectorielle. Erreur: {e}")
        db.rollback()
        raise

def seed_vector_store(db: Session, examples_filepath: str):
    """
    Lit un fichier JSON, génère les embeddings et peuple la base de données.
    """
    try:
        with open(examples_filepath, 'r', encoding='utf-8') as f:
            examples = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Erreur de lecture du fichier d'exemples '{examples_filepath}'. Erreur: {e}")
        return

    logger.info(f"Début du peuplement de la base vectorielle avec {len(examples)} exemples...")

    entries_to_add = []
    for i, example in enumerate(examples):
        text_to_embed = example.get("text")
        language = example.get("language")
        content_type = example.get("content_type")

        if not all([text_to_embed, language, content_type]):
            logger.warning(f"Exemple ignoré (champs manquants) : {example}")
            continue

        try:
            embedding = get_text_embedding(text_to_embed)
            if len(embedding) != VECTOR_DIMENSION:
                logger.error(f"Dimension de vecteur incorrecte pour l'exemple {i+1}. Attendu: {VECTOR_DIMENSION}, Obtenu: {len(embedding)}. L'exemple est ignoré.")
                continue

            vector_entry = VectorStore(
                chunk_text=text_to_embed,
                embedding=embedding,
                source_language=language,
                content_type=content_type
            )
            entries_to_add.append(vector_entry)
            logger.info(f"Exemple {i+1}/{len(examples)} vectorisé avec succès.")
        except Exception as e:
            logger.error(f"Erreur de vectorisation pour l'exemple {i+1}. Erreur: {e}")
            continue
    
    if not entries_to_add:
        logger.info("Aucun nouvel exemple à ajouter.")
        return

    try:
        db.add_all(entries_to_add)
        db.commit()
        logger.info(f"SUCCÈS : {len(entries_to_add)} exemples ont été ajoutés à la base vectorielle.")
    except Exception as e:
        logger.error(f"Erreur lors du commit final. Annulation. Erreur: {e}")
        db.rollback()

if __name__ == "__main__":
    db = SessionLocal()
    try:
        setup_database_extension(db)
        clear_vector_store(db)
        seed_vector_store(db, EXAMPLES_FILEPATH)
    finally:
        db.close()