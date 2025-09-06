import json
import logging
import sys
from pathlib import Path

from sqlalchemy.orm import Session
from tqdm import tqdm

# --- Configuration du chemin et des imports ---
sys.path.append(str(Path(__file__).resolve().parents[1]))

# --- Import de la base et de TOUS les modèles ---
from app.db.base import Base
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.analytics.vector_store_model import VectorStore
# --- Fin des imports de modèles ---

from app.db.session import SessionLocal
from app.services.rag_utils import get_embedding


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_FILES = [
    Path(__file__).resolve().parent.parent / "app" / "data" / "langues" / "kana.jsonl",
    Path(__file__).resolve().parent.parent / "app" / "data" / "langues" / "kanjis.jsonl",
    Path(__file__).resolve().parent.parent / "app" / "data" / "langues" / "vocabulaire.jsonl",
]

# --- Fonctions de Préparation du Texte (inchangées) ---
def format_kana_for_embedding(item):
    data = item.get('data', {})
    return f"Caractère japonais {data.get('script', '')} : {data.get('character', '')}, prononcé {data.get('romaji', '')}."

def format_kanji_for_embedding(item):
    data = item.get('data', {})
    return f"Kanji japonais : {data.get('character', '')}. Signification : {data.get('meaning', '')}. Lectures ON : {data.get('onyomi_romaji', '')}, Lectures KUN : {data.get('kunyomi_romaji', '')}."

def format_vocabulary_for_embedding(item):
    data = item.get('data', {})
    example = data.get('example_sentences', [{}])[0].get('fr', '')
    return f"Mot de vocabulaire japonais : {data.get('word', '')} ({data.get('reading', '')}). Signification : {data.get('meaning', '')}. Exemple : {example}"

CONTENT_TYPE_FORMATTERS = {
    "kana": format_kana_for_embedding,
    "kanji": format_kanji_for_embedding,
    "vocabulary": format_vocabulary_for_embedding
}

def seed_language_course_material():
    db: Session = SessionLocal()
    try:
        logger.info("--- Démarrage du seeding pour le matériel de cours de langue ---")

        logger.info("Suppression des anciennes entrées de cours de japonais...")
        num_deleted = db.query(VectorStore).filter(
            VectorStore.domain == 'language_learning',
            VectorStore.area == 'japanese'
        ).delete(synchronize_session=False)
        db.commit()
        if num_deleted > 0:
            logger.warning(f"🧹 {num_deleted} anciennes entrées ont été supprimées.")

        vectors_to_add = []
        total_count = 0

        for file_path in DATA_FILES:
            if not file_path.exists():
                logger.warning(f"Fichier non trouvé : {file_path}")
                continue

            logger.info(f"--- Traitement du fichier : {file_path.name} ---")

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in tqdm(lines, desc=f"Lecture de {file_path.name}"):
                    try:
                        item = json.loads(line)
                        content_type = item.get('content_type')

                        if not item.get('doc_id') or not content_type:
                            continue
                        
                        formatter = CONTENT_TYPE_FORMATTERS.get(content_type)
                        if not formatter:
                            continue
                            
                        document_text = formatter(item)
                        embedding_vector = get_embedding(document_text)

                        # --- CORRECTION ICI ---
                        # On retire l'argument 'metadata_' qui n'existe pas dans le modèle
                        new_vector = VectorStore(
                            chunk_text=document_text,
                            embedding=embedding_vector,
                            domain='language_learning',
                            area='japanese',
                            skill=content_type
                        )
                        # --- Fin de la correction ---
                        
                        vectors_to_add.append(new_vector)
                        total_count += 1

                    except json.JSONDecodeError:
                        logger.error(f"Erreur de décodage JSON pour la ligne : {line.strip()}")
                    except Exception as e:
                        logger.error(f"Erreur inattendue en traitant la ligne {line.strip()}: {e}")

        if vectors_to_add:
            logger.info(f"Ajout de {len(vectors_to_add)} nouveaux vecteurs à la base de données...")
            db.add_all(vectors_to_add)
            db.commit()
            logger.info(f"✅ SUCCÈS : {total_count} documents ont été vectorisés et ajoutés.")
        else:
            logger.info("ℹ️ Aucun document valide trouvé à ajouter.")

    except Exception as e:
        logger.error(f"❌ Une erreur critique est survenue durant le seeding : {e}", exc_info=True)
        db.rollback()
    finally:
        logger.info("--- Fin du script de seeding. Fermeture de la session DB. ---")
        db.close()


if __name__ == "__main__":
    seed_language_course_material()