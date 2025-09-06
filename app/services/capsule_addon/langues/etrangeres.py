# Fichier: backend/app/services/capsule_addon/langues/etrangeres.py (LOGIQUE CORRIGÉE)

import logging
from sqlalchemy import func
from app.models.capsule.capsule_model import Capsule
from .base_language_builder import BaseLanguageBuilder

logger = logging.getLogger(__name__)

class EtrangeresLanguageBuilder(BaseLanguageBuilder):
    def build(self):
        logger.info(f"--- [BUILDER_ETRANGERES] Début de la construction du parcours pour '{self.main_skill}' ---")

        # --- CORRECTION MAJEURE : On cherche d'abord un plan existant ---
        # On cherche une capsule "modèle" qui a le même main_skill et qui a déjà un plan.
        golden_record = self.db.query(Capsule).filter(
            func.lower(Capsule.main_skill) == self.main_skill.lower(),
            Capsule.learning_plan_json.isnot(None)
        ).first()

        if golden_record:
            logger.info(f"✅ Plan de cours trouvé dans la base de données pour '{self.main_skill}'. Utilisation directe.")
            return golden_record.learning_plan_json

        # --- Logique de repli (Fallback) ---
        # Si aucun plan n'est trouvé dans la DB, alors on passe à la génération.
        # Pour l'instant, nous pouvons laisser un message clair.
        # Plus tard, c'est ici qu'on appellera OpenAI.
        logger.warning(f"⚠️ Aucun plan de cours pré-chargé trouvé pour '{self.main_skill}'.")
        logger.warning("-> (Futur) Lancement de la génération via OpenAI...")
        
        # Pour éviter de planter, on retourne une structure de plan vide.
        # Cela indique que la génération doit se faire mais qu'aucun plan n'était disponible.
        return {
            "overview": f"Un nouveau cours pour apprendre le {self.main_skill}.",
            "levels": []
        }