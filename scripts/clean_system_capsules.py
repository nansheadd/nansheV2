import logging
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# --- Configuration ---
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa
from app.db.session import SessionLocal
from app.models.capsule.capsule_model import Capsule
from app.models.user.user_model import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_system_generated_capsules():
    """
    Supprime toutes les capsules créées par l'utilisateur système
    pour nettoyer la base de données après un mauvais seeding.
    """
    db: Session = SessionLocal()
    try:
        logger.info("--- Démarrage du nettoyage des capsules générées par le système ---")
        system_user = db.query(User).filter(User.email == "system@nanshe.ai").first()

        if not system_user:
            logger.warning("L'utilisateur système 'system@nanshe.ai' n'a pas été trouvé. Aucun nettoyage nécessaire.")
            return

        logger.info(f"Utilisateur système trouvé (ID: {system_user.id}). Recherche des capsules associées...")
        capsules_to_delete = db.query(Capsule).filter(Capsule.creator_id == system_user.id)
        count = capsules_to_delete.count()

        if count == 0:
            logger.info("Aucune capsule créée par le système à supprimer.")
            return

        logger.warning(f"{count} capsules créées par le système ont été trouvées. Suppression en cours...")
        capsules_to_delete.delete(synchronize_session=False)
        db.commit()
        logger.info(f"✅ SUCCÈS : {count} capsules ont été supprimées.")

    except Exception as e:
        logger.error(f"❌ Une erreur est survenue durant le nettoyage : {e}", exc_info=True)
        db.rollback()
    finally:
        logger.info("--- Fin du script de nettoyage ---")
        db.close()

if __name__ == "__main__":
    clean_system_generated_capsules()