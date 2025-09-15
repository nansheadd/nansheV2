# app/services/atom_service.py

import json
from sqlalchemy.orm import Session
from app.core import ai_service
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from typing import Dict, Any, Optional
from app.models.capsule.atom_model import Atom, AtomContentType

class AtomService:
    """
    Service dédié à la création et à la gestion des Atomes.
    Contient la logique spécifique pour chaque type d'atome.
    """
    def __init__(self, db: Session, user: User, capsule: Capsule):
        self.db = db
        self.user = user
        self.capsule = capsule

    def create_atom_content(self, atom_type: AtomContentType, molecule: Molecule, context_atoms: list[Atom], difficulty: Optional[str] = None) -> Dict[str, Any] | None:
        """Aiguille vers la bonne méthode de création en fonction du type d'atome."""
        if atom_type == AtomContentType.LESSON:
            return self._create_lesson_content(molecule)
        if atom_type == AtomContentType.QUIZ:
            return self._create_quiz_content(molecule, context_atoms, difficulty)
        # Ajoutez d'autres types d'atomes ici à l'avenir
        # if atom_type == AtomContentType.CODE_CHALLENGE:
        #     return self._create_code_challenge_content(molecule)
        return None

    def _create_lesson_content(self, molecule: Molecule) -> Dict[str, Any]:
        """
        Crée le contenu pour un atome de type Leçon en reconstruisant
        le contexte du plan depuis la base de données.
        """
        
        # --- CORRECTION : Reconstruire le contexte du plan ---
        # Au lieu de lire un champ JSON, nous créons un dictionnaire
        # à partir des relations SQLAlchemy déjà chargées.
        plan_dict = {
            "overview": {
                "title": self.capsule.title,
                "domain": self.capsule.domain,
                "main_skill": self.capsule.main_skill,
            },
            "granules": [
                {
                    "title": granule.title,
                    "order": granule.order,
                    "molecules": [
                        {"title": m.title, "order": m.order}
                        for m in sorted(granule.molecules, key=lambda x: x.order)
                    ]
                }
                for granule in sorted(self.capsule.granules, key=lambda x: x.order)
            ]
        }
        plan_context = json.dumps(plan_dict, indent=2, ensure_ascii=False)
        # --- FIN DE LA CORRECTION ---

        app_rules_context = """
        - Structure: Le cours est divisé en chapitres (granules) et leçons (molécules).
        - Calendrier: L'apprentissage est auto-rythmé (self-paced).
        - Évaluations: Chaque leçon est typiquement suivie d'un quiz simple (QCM).
        """
        
        # Le reste de la fonction est maintenant correct
        return ai_service.generate_contextual_lesson(
            course_plan_context=plan_context,
            app_rules_context=app_rules_context,
            target_lesson_title=molecule.title,
            model_choice="gpt-5-mini-2025-08-07"
        )

    def _create_quiz_content(self, molecule: Molecule, context_atoms: list[Atom], difficulty: Optional[str]) -> Dict[str, Any] | None:
        """
        Crée le contenu pour un atome de type Quiz en utilisant la nouvelle
        fonction de génération contextualisée.
        """
        lesson_text = ""
        for atom in context_atoms:
            if atom.content_type == AtomContentType.LESSON:
                lesson_text = atom.content.get("text", "")
                break
        
        if not lesson_text:
            print(f"Impossible de créer un quiz pour '{molecule.title}' car le contenu de la leçon est manquant.")
            return None

        # --- On appelle la NOUVELLE fonction de l'ai_service ---
        exercise_content = ai_service.generate_contextual_exercises(
            lesson_text=lesson_text,
            lesson_title=molecule.title,
            course_type="generic",
            difficulty=difficulty, # <-- On le passe à l'IA
            model_choice="gpt-5-mini-2025-08-07"
        )
        
        # La nouvelle fonction renvoie directement le bon format JSON,
        # donc on peut le retourner tel quel.
        if exercise_content:
            return exercise_content
            
        return None