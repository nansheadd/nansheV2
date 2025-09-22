from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.capsule.atom_model import AtomContentType, Atom
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.user.user_model import User
from app.services.atom_service import AtomService
from app.services.services.capsules.base_builder import BaseCapsuleBuilder


SCIENCE_DOMAINS = {
    "science",
    "sciences",
    "natural_sciences",
    "physical_sciences",
    "mathematics",
    "math",
    "maths",
    "engineering",
    "biology",
    "chemistry",
    "physics",
}


class ScienceBuilder(BaseCapsuleBuilder):
    """
    Capsule builder dédié aux sciences "dures" : mathématiques, physique, chimie, biologie.

    Il assemble un panel d'atomes variés (leçon, flashcards, exercices guidés
    et évaluations) adaptés aux besoins des matières scientifiques.
    """

    SUPPORTED_DOMAINS = SCIENCE_DOMAINS

    def __init__(
        self,
        db: Session,
        capsule: Capsule,
        user: User,
        *,
        source_material: Optional[dict] = None,
    ):
        super().__init__(db=db, capsule=capsule, user=user, source_material=source_material)
        self.atom_service = AtomService(
            db=db,
            user=user,
            capsule=capsule,
            source_material=source_material,
        )
        self._ensure_enum_values()

    # ------------------------------------------------------------------
    # Recette d'une molécule scientifique
    # ------------------------------------------------------------------
    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        area = (self.capsule.area or "").lower()
        is_mathematics = any(keyword in area for keyword in ("math", "algebra", "geometry", "calculus", "probability", "statistics"))
        is_chemistry = "chem" in area
        is_physics = "phys" in area

        recipe: List[Dict[str, Any]] = [
            {"type": AtomContentType.LESSON, "title": "Concept clé"},
            {"type": AtomContentType.FLASHCARDS, "title": "Notions à mémoriser"},
            {"type": AtomContentType.FILL_IN_THE_BLANK, "title": "Texte à trous"},
            {"type": AtomContentType.TRUE_FALSE, "title": "Validation express"},
            {"type": AtomContentType.SHORT_ANSWER, "title": "Question courte"},
            {"type": AtomContentType.MATCHING, "title": "Associer les notions"},
            {"type": AtomContentType.ORDERING, "title": "Remettre dans l'ordre"},
        ]

        if is_mathematics:
            recipe.append({"type": AtomContentType.QUIZ, "title": "Quiz de calcul", "difficulty": "moyen"})
            recipe.append({"type": AtomContentType.CATEGORIZATION, "title": "Classer les objets"})
        if is_chemistry:
            recipe.append({"type": AtomContentType.DIAGRAM_COMPLETION, "title": "Compléter le schéma"})
        if is_physics:
            recipe.append({"type": AtomContentType.QUIZ, "title": "Quiz de raisonnement", "difficulty": "difficile"})

        return recipe

    # ------------------------------------------------------------------
    # Création de contenu d'atome
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_enum_values(self) -> None:
        targets = {
            AtomContentType.FILL_IN_THE_BLANK.value,
            AtomContentType.FLASHCARDS.value,
            AtomContentType.SHORT_ANSWER.value,
            AtomContentType.TRUE_FALSE.value,
            AtomContentType.MATCHING.value,
            AtomContentType.ORDERING.value,
            AtomContentType.CATEGORIZATION.value,
            AtomContentType.DIAGRAM_COMPLETION.value,
        }

        bind = self.db.get_bind()
        if bind is None:
            return

        try:
            with bind.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                existing = {
                    row[0]
                    for row in connection.execute(
                        text("SELECT unnest(enum_range(NULL::atom_content_type_enum))")
                    )
                }

                candidates = set()
                for value in targets:
                    candidates.add(value)
                    candidates.add(value.upper())

                for candidate in sorted(candidates):
                    if candidate not in existing:
                        connection.execute(
                            text("ALTER TYPE atom_content_type_enum ADD VALUE IF NOT EXISTS :val"),
                            {"val": candidate},
                        )
                        existing.add(candidate)
        except ProgrammingError:
            self.db.rollback()
