# Fichier: backend/app/services/capsule_addon/langues/base_language_builder.py (CORRIGÉ)

import logging
from sqlalchemy.orm import Session
from abc import ABC, abstractmethod
from app.models.capsule.capsule_model import Capsule

logger = logging.getLogger(__name__)

class BaseLanguageBuilder(ABC):
    def __init__(self, db: Session, capsule: Capsule):
        self.db = db
        self.capsule = capsule
        # --- CORRECTION : On utilise main_skill ---
        self.main_skill = capsule.main_skill
        logger.info(f"--- [BUILDER_BASE] Initialisé pour la capsule '{capsule.title}' (Skill: {self.main_skill}) ---")

    @abstractmethod
    def build(self):
        pass

    def _get_knowledge_atoms(self, skill: str, content_type: str):
        from app.models.analytics.vector_store_model import VectorStore
        
        logger.info(f"  [BUILDER_BASE] Récupération des atomes: skill='{skill}', content_type='{content_type}' pour la langue '{self.main_skill}'")
        
        # --- CORRECTION : La requête filtre maintenant correctement ---
        # On cherche les atomes où 'area' est la langue (ex: 'japanese') et 'skill' est le type d'alphabet (ex: 'hiragana')
        atoms = self.db.query(VectorStore).filter(
            VectorStore.area == self.main_skill.lower(),
            VectorStore.skill == skill,
            VectorStore.content_type == content_type
        ).all()
        
        logger.info(f"  [BUILDER_BASE] -> {len(atoms)} atomes trouvés.")
        return atoms