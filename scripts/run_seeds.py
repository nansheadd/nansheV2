# Fichier: backend/scripts/run_seeds.py

import json
import logging
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func

# --- Configuration du chemin et des imports ---
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa: F401 - Crucial pour charger tous les modèles
from app.db.session import SessionLocal
from app.models.capsule.capsule_model import Capsule, GenerationStatus
from app.models.analytics.vector_store_model import VectorStore
from app.models.user.user_model import User
from app.services.rag_utils import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Chemins vers les fichiers de données ---
CLASSIFIER_TRAINING_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "training_data.jsonl"
PLANS_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "plan_foreing_langue.jsonl"


def get_or_create_default_user(db: Session) -> User:
    """Récupère ou crée un utilisateur système pour être le créateur des capsules modèles."""
    system_user = db.query(User).filter(User.email == "system@nanshe.ai").first()
    if not system_user:
        logger.info("Création de l'utilisateur système 'system@nanshe.ai'")
        system_user = User(
            username="system", email="system@nanshe.ai",
            hashed_password="password", is_active=True, is_superuser=True
        )
        db.add(system_user)
        db.commit(); db.refresh(system_user)
    return system_user

def seed_classifier_examples(db: Session):
    """Charge les exemples de phrases d'entraînement dans la VectorStore."""
    logger.info("--- Phase 1: Seeding des exemples du classifieur ---")
    if not CLASSIFIER_TRAINING_FILE.exists():
        logger.error(f"❌ Fichier d'entraînement non trouvé : {CLASSIFIER_TRAINING_FILE}")
        return

    count = 0
    with open(CLASSIFIER_TRAINING_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                text = data.get("text")
                main_skill = data.get("main_skill") or data.get("label")

                if not text or not main_skill: continue

                # On vérifie si cet exemple exact existe déjà pour ne pas le dupliquer
                exists = db.query(VectorStore).filter(VectorStore.chunk_text == text).first()
                if not exists:
                    new_vector = VectorStore(
                        chunk_text=text, embedding=get_embedding(text),
                        domain=data.get("domain", "unknown"),
                        area=data.get("area", "unknown"),
                        skill=main_skill
                    )
                    db.add(new_vector)
                    count += 1
            except json.JSONDecodeError:
                continue
    db.commit()
    logger.info(f"✅ Phase 1 terminée: {count} nouveaux exemples d'entraînement ajoutés.")


def seed_golden_learning_plans(db: Session, system_user: User):
    """Charge les plans de cours complets (golden records) dans les tables Capsule et VectorStore."""
    logger.info("--- Phase 2: Seeding des plans de cours 'golden records' ---")
    if not PLANS_FILE.exists():
        logger.error(f"❌ Fichier de plans non trouvé : {PLANS_FILE}")
        return

    count_added = 0
    count_updated = 0
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                main_skill = data.get("main_skill")
                if not main_skill: continue

                # On cherche une capsule existante pour ce main_skill (insensible à la casse)
                capsule = db.query(Capsule).filter(func.lower(Capsule.main_skill) == main_skill.lower()).first()

                if capsule:
                    capsule.learning_plan_json = data.get("learning_plan")
                    count_updated += 1
                else:
                    capsule = Capsule(
                        title=f"Cours de {main_skill.capitalize()}", main_skill=main_skill,
                        domain=data.get("domain"), area=data.get("area"),
                        learning_plan_json=data.get("learning_plan"),
                        creator_id=system_user.id, generation_status=GenerationStatus.COMPLETED,
                        is_public=True
                    )
                    db.add(capsule)
                    count_added += 1

                # On ajoute une entrée DÉDIÉE au main_skill dans la VectorStore pour la recherche exacte
                vector_exists = db.query(VectorStore).filter(
                    func.lower(VectorStore.skill) == main_skill.lower(),
                    VectorStore.chunk_text == main_skill # Entrée exacte
                ).first()
                if not vector_exists:
                     db.add(VectorStore(
                        chunk_text=main_skill, embedding=get_embedding(main_skill),
                        domain=data.get("domain"), area=data.get("area"), skill=main_skill
                    ))
            except json.JSONDecodeError:
                continue
    db.commit()
    logger.info(f"✅ Phase 2 terminée: {count_added} plans ajoutés, {count_updated} mis à jour.")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        # On récupère l'utilisateur système une seule fois
        user = get_or_create_default_user(db_session)
        # On exécute les deux phases de seeding
        seed_classifier_examples(db_session)
        seed_golden_learning_plans(db_session, user)
    finally:
        db_session.close()