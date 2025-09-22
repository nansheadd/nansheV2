import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

# --- Imports de votre application ---
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom, AtomContentType
from app.services.atom_service import AtomService
from app.core import ai_service
from app.services.services.capsules.base_builder import BaseCapsuleBuilder

class DefaultBuilder(BaseCapsuleBuilder):
    """
    Builder générique qui orchestre la création de contenu en déléguant
    la logique de fabrication des atomes à l'AtomService.
    """

    def __init__(
        self,
        db: Session,
        capsule: Capsule,
        user: User,
        *,
        source_material: Optional[dict] = None,
    ):
        """ Initialise le builder et le service d'atomes associé. """
        super().__init__(db=db, capsule=capsule, user=user, source_material=source_material)
        self.atom_service = AtomService(
            db=db,
            user=user,
            capsule=capsule,
            source_material=source_material,
        )

    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        """
        Définit une recette avec une leçon et trois QCM à difficulté croissante.
        """
        return [
            {"type": AtomContentType.LESSON, "title": "Leçon"},
            {"type": AtomContentType.QUIZ, "title": "Quiz (Facile)", "difficulty": "facile"},
            {"type": AtomContentType.QUIZ, "title": "Quiz (Moyen)", "difficulty": "moyen"},
            {"type": AtomContentType.QUIZ, "title": "Quiz (Difficile)", "difficulty": "difficile"}
        ]

    def _build_atom_content(
        self,
        atom_type: AtomContentType,
        molecule: Molecule,
        context_atoms: List[Atom],
        difficulty: Optional[str] = None  # <-- CORRECTION : AJOUT DU PARAMÈTRE MANQUANT
    ) -> Dict[str, Any] | None:
        """
        Délègue la création du contenu à l'AtomService, en passant la difficulté.
        """
        # On passe maintenant la difficulté au service
        return self.atom_service.create_atom_content(
            atom_type,
            molecule,
            context_atoms,
            difficulty=difficulty # <-- On transmet l'argument
        )

    def _generate_plan_from_source(
        self,
        db: Session,
        capsule: Capsule,
        source_material: dict,
    ) -> dict | None:
        document_text = (source_material or {}).get("text")
        if not document_text:
            return None
        try:
            return ai_service.generate_learning_plan_from_document(
                document_text=document_text,
                title=capsule.title,
                domain=capsule.domain,
                area=capsule.area,
                main_skill=capsule.main_skill,
                model_choice="gpt-5-mini-2025-08-07",
            )
        except Exception as exc:
            logger = logging.getLogger(__name__)
            logger.error("Echec génération plan contextualisé: %s", exc, exc_info=True)
            return None
