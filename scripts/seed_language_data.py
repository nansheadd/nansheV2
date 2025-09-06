import json
import logging
import sys
from pathlib import Path

from sqlalchemy.orm import Session
from tqdm import tqdm

# --- Configuration du chemin et des imports ---
# Ajoute le répertoire parent au path pour permettre les imports relatifs de l'application
sys.path.append(str(Path(__file__).resolve().parents[1]))

# --- SOLUTION: Importer la base et TOUS les modèles ici ---
# Cette étape est CRUCIALE. Elle charge tous les modèles dans les métadonnées de SQLAlchemy
# avant que nous n'essayions d'interagir avec la base de données, résolvant ainsi les
# erreurs de "failed to locate a name".
from app.db.base import Base
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.analytics.vector_store_model import VectorStore
# Ajoutez d'autres imports de modèles si nécessaire pour couvrir toutes les relations
# --- Fin de la solution ---

from app.db.session import SessionLocal
from app.services.rag_utils import get_embedding


# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Liste des fichiers de données à traiter
DATA_FILES = [
    Path(__file__).resolve().parent.parent / "app" / "data" / "langues" / "kana.jsonl",
    Path(__file__).resolve().parent.parent / "app" / "data" / "langues" / "kanjis.jsonl",
    Path(__file__).resolve().parent.parent / "app" / "data" / "langues" / "vocabulaire.jsonl",
]

# --- Fonctions de Préparation du Texte ---

def format_kana_for_embedding(item):
    """Crée une phrase descriptive pour un kana."""
    data = item.get('data', {})
    return f"Caractère japonais {data.get('script', '')} : {data.get('character', '')}, prononcé {data.get('romaji', '')}."

def format_kanji_for_embedding(item):
    """Crée une phrase descriptive pour un kanji."""
    data = item.get('data', {})
    return f"Kanji japonais : {data.get('character', '')}. Signification : {data.get('meaning', '')}. Lectures ON : {data.get('onyomi_romaji', '')}, Lectures KUN : {data.get('kunyomi_romaji', '')}."

def format_vocabulary_for_embedding(item):
    """Crée une phrase descriptive pour un mot de vocabulaire."""
    data = item.get('data', {})
    example = data.get('example_sentences', [{}])[0].get('fr', '')
    return f"Mot de vocabulaire japonais : {data.get('word', '')} ({data.get('reading', '')}). Signification : {data.get('meaning', '')}. Exemple : {example}"

# Mapping entre le type de contenu et la fonction de formatage
CONTENT_TYPE_FORMATTERS = {
    "kana": format_kana_for_embedding,
    "kanji": format_kanji_for_embedding,
    "vocabulary": format_vocabulary_for_embedding
}

# --- Script Principal ---

def seed_language_course_material():
    """
    Script principal pour lire les fichiers JSONL de cours de langue, créer les embeddings,
    et les stocker dans la table VectorStore via SQLAlchemy.
    """
    db: Session = SessionLocal()
    try:
        logger.info("--- Démarrage du seeding pour le matériel de cours de langue ---")

        # 1. Nettoyer les anciennes entrées pour ce matériel de cours spécifique
        logger.info("Suppression des anciennes entrées de cours de japonais pour éviter les doublons...")
        num_deleted = db.query(VectorStore).filter(
            VectorStore.domain == 'language_learning',
            VectorStore.area == 'japanese'
        ).delete(synchronize_session=False)
        db.commit()
        if num_deleted > 0:
            logger.warning(f"🧹 {num_deleted} anciennes entrées ont été supprimées de la table VectorStore.")

        vectors_to_add = []
        total_count = 0

        # 2. Traiter chaque fichier de données
        for file_path in DATA_FILES:
            if not file_path.exists():
                logger.warning(f"Le fichier {file_path} n'a pas été trouvé. Passage au suivant.")
                continue

            logger.info(f"--- Traitement du fichier : {file_path.name} ---")

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in tqdm(lines, desc=f"Lecture de {file_path.name}"):
                    try:
                        item = json.loads(line)
                        content_type = item.get('content_type')

                        if not item.get('doc_id') or not content_type:
                            logger.warning(f"Ligne ignorée (doc_id ou content_type manquant): {line.strip()}")
                            continue
                        
                        formatter = CONTENT_TYPE_FORMATTERS.get(content_type)
                        if not formatter:
                            logger.warning(f"Aucun formateur trouvé pour le content_type '{content_type}'. Ligne ignorée.")
                            continue
                            
                        document_text = formatter(item)
                        embedding_vector = get_embedding(document_text)

                        new_vector = VectorStore(
                            chunk_text=document_text,
                            embedding=embedding_vector,
                            domain='language_learning',
                            area='japanese',
                            skill=content_type,
                            metadata_=item 
                        )
                        vectors_to_add.append(new_vector)
                        total_count += 1

                    except json.JSONDecodeError:
                        logger.error(f"Erreur de décodage JSON pour la ligne : {line.strip()}")
                    except Exception as e:
                        logger.error(f"Erreur inattendue en traitant la ligne {line.strip()}: {e}")

        # 3. Ajouter tous les nouveaux vecteurs à la base de données en une seule fois
        if vectors_to_add:
            logger.info(f"Ajout de {len(vectors_to_add)} nouveaux vecteurs à la base de données...")
            db.add_all(vectors_to_add)
            db.commit()
            logger.info(f"✅ SUCCÈS : {total_count} documents de cours de langue ont été vectorisés et ajoutés.")
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