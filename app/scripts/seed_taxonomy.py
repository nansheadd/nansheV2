import json
import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore
from sentence_transformers import SentenceTransformer
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Le sujet EXACT qui servira de clé de recherche pour ce plan
COURSE_SKILL = "apprendre le japonais" 
# Le chemin vers votre fichier JSON
PLAN_FILEPATH = "app/data/japanese_course_plan.json"
MODEL_NAME = 'all-MiniLM-L6-v2'

def seed_single_course_plan(db: Session):
    """
    Lit un fichier de plan de cours JSON, le vectorize comme un document unique,
    et l'insère dans la base de données vectorielle.
    """
    # Détection du device (mps pour Mac M1/M2/M3, etc.)
    if torch.cuda.is_available():
        device = 'cuda'
    elif torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
    logger.info(f"Chargement du modèle sur le device : '{device}'...")
    model = SentenceTransformer(MODEL_NAME, device=device)

    try:
        with open(PLAN_FILEPATH, 'r', encoding='utf-8') as f:
            plan_json = json.load(f)
    except Exception as e:
        logger.error(f"Erreur de lecture du fichier '{PLAN_FILEPATH}': {e}")
        return

    # Convertir le JSON entier en une chaîne de texte pour l'embedding
    plan_text = json.dumps(plan_json, indent=2, ensure_ascii=False)
    
    logger.info(f"Vectorisation du plan de cours pour '{COURSE_SKILL}'...")
    embedding = model.encode(plan_text)

    # Supprimer l'ancienne version si elle existe pour éviter les doublons
    db.query(VectorStore).filter(
        VectorStore.content_type == 'course_plan',
        VectorStore.skill == COURSE_SKILL
    ).delete()
    db.commit()

    # Créer la nouvelle entrée
    plan_entry = VectorStore(
        chunk_text=plan_text,
        embedding=embedding,
        domain="langues",
        area="langues_etrangeres",
        skill=COURSE_SKILL,
        content_type="course_plan"
    )

    db.add(plan_entry)
    db.commit()
    logger.info(f"✅ SUCCÈS : Le plan de cours pour '{COURSE_SKILL}' a été ajouté à la base vectorielle.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_single_course_plan(db)
    finally:
        db.close()