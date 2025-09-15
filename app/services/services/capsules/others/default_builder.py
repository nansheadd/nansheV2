from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

# --- Imports de votre application ---
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom, AtomContentType
from app.services.atom_service import AtomService
from app.services.services.capsules.base_builder import BaseCapsuleBuilder

class DefaultBuilder(BaseCapsuleBuilder):
    """
    Builder générique qui orchestre la création de contenu en déléguant
    la logique de fabrication des atomes à l'AtomService.
    """

    def __init__(self, db: Session, capsule: Capsule, user: User):
        """ Initialise le builder et le service d'atomes associé. """
        super().__init__(db=db, capsule=capsule, user=user)
        self.atom_service = AtomService(db=db, user=user, capsule=capsule)

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