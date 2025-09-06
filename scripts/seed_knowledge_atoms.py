import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore
from app.services.rag_utils import get_embedding # On réutilise votre fonction d'embedding
from app.db.base import Base  # Assurez-vous que tous les modèles sont chargés

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chemin vers votre fichier de données
SCRIPT_DIR = Path(__file__).parent
DATA_FILE = SCRIPT_DIR / "lo.json" # On suppose que lo.json est dans le même dossier que le script
# --------------------------------

def seed_atoms(db: Session, filepath: str):
    """
    Lit un fichier JSON d'atomes de connaissance et les peuple dans la base vectorielle.
    """
    logger.info(f"--- Début du seeding des atomes de connaissance depuis '{filepath}' ---")
    try:
        # On utilise directement le chemin corrigé
        with open(filepath, 'r', encoding='utf-8') as f:
            knowledge_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"ERREUR: Le fichier de données '{filepath}' n'a pas été trouvé.")
        return

    domain = knowledge_data.get("domain")
    area = knowledge_data.get("area")
    atoms = knowledge_data.get("knowledge_atoms", [])

    if not all([domain, area, atoms]):
        logger.error("ERREUR: Le fichier JSON est mal formaté. Les clés 'domain', 'area', ou 'knowledge_atoms' sont manquantes.")
        return

    entries_to_add = []
    logger.info(f"Préparation de {len(atoms)} atomes pour le domaine '{domain}' et la zone '{area}'...")

    for i, atom in enumerate(atoms):
        skill = atom.get("skill")
        content_type = atom.get("content_type")
        data = atom.get("data")

        if not all([skill, content_type, data]):
            logger.warning(f"Atome n°{i+1} ignoré (champs manquants).")
            continue

        # Le chunk_text est l'objet 'data' lui-même, converti en chaîne JSON.
        # C'est cette chaîne que le LLM recevra comme contexte.
        chunk_text = json.dumps(data, ensure_ascii=False)
        
        # On génère l'embedding à partir de cette même chaîne JSON
        embedding = get_embedding(chunk_text)

        vector_entry = VectorStore(
            chunk_text=chunk_text,
            embedding=embedding,
            domain=domain,
            area=area,
            skill=skill,
            content_type=content_type
        )
        entries_to_add.append(vector_entry)
        logger.info(f" -> Atome n°{i+1} ({content_type} / {skill}) traité.")

    if not entries_to_add:
        logger.info("Aucun nouvel atome à ajouter.")
        return

    try:
        db.add_all(entries_to_add)
        db.commit()
        logger.info(f"✅ SUCCÈS : {len(entries_to_add)} atomes de connaissance ont été ajoutés à la base vectorielle.")
    except Exception as e:
        logger.error(f"ERREUR lors du commit final en base de données: {e}", exc_info=True)
        db.rollback()

if __name__ == "__main__":
    db = SessionLocal()
    try:
        # Vous pouvez ajouter une fonction pour nettoyer la DB ici si nécessaire
        seed_atoms(db, DATA_FILE)
    finally:
        db.close()