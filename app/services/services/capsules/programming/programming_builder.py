from __future__ import annotations

from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models.capsule.atom_model import Atom, AtomContentType
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.user.user_model import User
from app.services.atom_service import AtomService
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from app.core import ai_service


class ProgrammingBuilder(BaseCapsuleBuilder):
    """Builder générique pour les capsules de programmation (Python, JS, SQL, etc.)."""

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
        self.language = self._detect_language()

    # -----------------------------
    # Helpers
    # -----------------------------

    def _detect_language(self) -> str:
        text = " ".join(
            filter(
                None,
                [
                    (self.capsule.main_skill or ""),
                    (self.capsule.area or ""),
                    (self.capsule.description or ""),
                ],
            )
        ).lower()

        language_map = {
            'python': 'python',
            'py': 'python',
            'javascript': 'javascript',
            'typescript': 'javascript',
            'node': 'javascript',
            'js': 'javascript',
            'react': 'javascript',
            'sql': 'sql',
            'postgres': 'sql',
            'postgresql': 'sql',
            'mysql': 'sql',
            'sqlite': 'sql',
            'java ': 'java',
            'kotlin': 'java',
            'swift': 'swift',
            'go ': 'go',
            'rust': 'rust',
            'c#': 'csharp',
            'c++': 'cpp',
            'php': 'php',
        }

        for key, lang in language_map.items():
            if key in text:
                return lang

        return 'python'

    # -----------------------------
    # Overrides
    # -----------------------------

    def generate_learning_plan(self, db: Session, capsule: Capsule) -> Dict[str, Any] | None:
        if self.source_material:
            plan_from_source = self._generate_plan_from_source(db, capsule, self.source_material)
            if plan_from_source:
                return plan_from_source
        existing_plan = self._find_plan_in_vector_store(db, capsule.main_skill)
        if existing_plan:
            return existing_plan

        rag_examples = self._find_inspirational_examples(db, capsule.domain, capsule.area)
        plan = ai_service.generate_programming_learning_plan(
            main_skill=capsule.main_skill,
            language=self.language,
            rag_examples=rag_examples,
            model_choice="gpt-5-mini-2025-08-07",
        )
        if not plan:
            return super().generate_learning_plan(db, capsule)

        self._save_plan_to_vector_store(db, capsule, plan)
        return plan

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
        except Exception:
            return None

    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        label = self.language.capitalize()
        progression = self.atom_service.compute_progression_stage(molecule)
        stage_difficulty = progression.get("difficulty", "intermédiaire")

        return [
            {"type": AtomContentType.LESSON, "title": f"Concept clé ({label})"},
            {"type": AtomContentType.CODE_EXAMPLE, "title": "Exemple guidé"},
            {"type": AtomContentType.QUIZ, "title": "Quiz de compréhension", "difficulty": "moyen"},
            {
                "type": AtomContentType.LIVE_CODE_EXECUTOR,
                "title": "Atelier interactif",
                "difficulty": stage_difficulty,
            },
            {
                "type": AtomContentType.CODE_CHALLENGE,
                "title": "Challenge pratique",
                "difficulty": stage_difficulty,
            },
            {
                "type": AtomContentType.CODE_SANDBOX_SETUP,
                "title": "Prépare ton espace sécurisé",
                "difficulty": stage_difficulty,
            },
            {
                "type": AtomContentType.CODE_PROJECT_BRIEF,
                "title": f"Projet de validation — {progression.get('label', 'Parcours')}",
                "difficulty": stage_difficulty,
            },
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
