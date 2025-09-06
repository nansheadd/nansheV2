# Fichier: backend/scripts/seed_learning_plans.py

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

# --- Chemin vers votre nouveau fichier de plans ---
PLANS_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "plan_foreign_langue.jsonl"

def get_or_create_default_user(db: Session) -> User:
    """Récupère ou crée un utilisateur système pour être le créateur des capsules modèles."""
    system_user = db.query(User).filter(User.email == "system@nanshe.ai").first()
    if not system_user:
        logger.info("Création de l'utilisateur système 'system@nanshe.ai'")
        # Note: Le mot de passe n'a pas d'importance car cet utilisateur ne se connectera pas.
        system_user = User(
            username="system",
            email="system@nanshe.ai",
            hashed_password="dummy_password", # Mettre une valeur factice
            is_active=True,
            is_superuser=True
        )
        db.add(system_user)
        db.commit()
        db.refresh(system_user)
    return system_user

def seed_golden_learning_plans():
    """
    Lit un fichier .jsonl contenant des plans de cours complets et les charge
    dans la base de données (Capsules et VectorStore) comme "golden records".
    """
    db: Session = SessionLocal()
    try:
        logger.info("--- Démarrage du seeding des plans de cours 'golden records' ---")

        if not PLANS_FILE.exists():
            logger.error(f"❌ Fichier de plans non trouvé : {PLANS_FILE}")
            return
        logger.info(f"✅ Fichier de plans trouvé : {PLANS_FILE.name}")

        system_user = get_or_create_default_user(db)
        count_added = 0
        count_skipped = 0

        with open(PLANS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    main_skill = data.get("main_skill")
                    domain = data.get("domain")
                    area = data.get("area")
                    learning_plan = data.get("learning_plan")

                    if not all([main_skill, domain, area, learning_plan]):
                        logger.warning(f"Ligne ignorée (données manquantes): {line.strip()[:100]}...")
                        continue

                    # 1. Vérifier si une capsule pour ce 'main_skill' existe déjà
                    # On compare en ignorant la casse pour plus de robustesse
                    existing_capsule = db.query(Capsule).filter(func.lower(Capsule.main_skill) == main_skill.lower()).first()
                    if existing_capsule:
                        logger.info(f"  -> La capsule pour '{main_skill}' existe déjà. Mise à jour du plan...")
                        existing_capsule.learning_plan_json = learning_plan
                        count_skipped += 1
                    else:
                        logger.info(f"  -> Création de la capsule pour '{main_skill}'...")
                        new_capsule = Capsule(
                            title=f"Cours de {main_skill.capitalize()}",
                            main_skill=main_skill,
                            domain=domain,
                            area=area,
                            learning_plan_json=learning_plan,
                            creator_id=system_user.id,
                            generation_status=GenerationStatus.COMPLETED,
                            is_public=True # Ces capsules modèles sont publiques
                        )
                        db.add(new_capsule)
                        count_added += 1
                    
                    # 2. Mettre à jour ou créer l'entrée dans la VectorStore
                    # Cela garantit que le classifieur peut trouver ce plan.
                    # Le texte de référence est le 'main_skill' lui-même.
                    vector_entry = db.query(VectorStore).filter(func.lower(VectorStore.skill) == main_skill.lower()).first()
                    if not vector_entry:
                        logger.info(f"     -> Création de l'entrée vectorielle pour '{main_skill}'")
                        new_vector = VectorStore(
                            chunk_text=main_skill,
                            embedding=get_embedding(main_skill),
                            domain=domain,
                            area=area,
                            skill=main_skill
                        )
                        db.add(new_vector)

                except json.JSONDecodeError:
                    logger.warning(f"Ligne JSON malformée ignorée : {line.strip()[:100]}...")

        db.commit()
        logger.info(f"✅ SUCCÈS : {count_added} nouveaux plans ont été ajoutés, {count_skipped} ont été mis à jour.")

    except Exception as e:
        logger.error(f"❌ Une erreur critique est survenue : {e}", exc_info=True)
        db.rollback()
    finally:
        logger.info("--- Fin du seeding des plans. Fermeture de la session DB. ---")
        db.close()

if __name__ == "__main__":
    seed_golden_learning_plans()