from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models.capsule.atom_model import Atom, AtomContentType
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.user.user_model import User
from app.services.atom_service import AtomService
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from app.core import ai_service


class PythonProgrammingBuilder(BaseCapsuleBuilder):
    """Builder spécialisé pour les capsules de programmation Python."""

    def __init__(self, db: Session, capsule: Capsule, user: User):
        super().__init__(db=db, capsule=capsule, user=user)
        self.atom_service = AtomService(db=db, user=user, capsule=capsule)

    def generate_learning_plan(self, db: Session, capsule: Capsule) -> Dict[str, Any] | None:
        existing_plan = self._find_plan_in_vector_store(db, capsule.main_skill)
        if existing_plan:
            return existing_plan

        rag_examples = self._find_inspirational_examples(db, capsule.domain, capsule.area)
        plan = ai_service.generate_programming_learning_plan(
            main_skill=capsule.main_skill,
            language='python',
            rag_examples=rag_examples,
            model_choice="gpt-5-mini-2025-08-07",
        )
        if not plan:
            return super().generate_learning_plan(db, capsule)

        self._save_plan_to_vector_store(db, capsule, plan)
        return plan

    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        """Définit la recette d'une leçon de programmation."""
        return [
            {"type": AtomContentType.LESSON, "title": "Concept clé"},
            {"type": AtomContentType.CODE_EXAMPLE, "title": "Exemple guidé"},
            {"type": AtomContentType.QUIZ, "title": "Quiz de compréhension", "difficulty": "moyen"},
            {"type": AtomContentType.CODE_CHALLENGE, "title": "Challenge pratique"},
            {"type": AtomContentType.LIVE_CODE_EXECUTOR, "title": "Atelier interactif"},
        ]

    def _build_atom_content(
        self,
        atom_type: AtomContentType,
        molecule: Molecule,
        context_atoms: List[Atom],
        difficulty: Optional[str] = None,
    ) -> Dict[str, Any] | None:
        return self.atom_service.create_atom_content(
            atom_type=atom_type,
            molecule=molecule,
            context_atoms=context_atoms,
            difficulty=difficulty,
        )
