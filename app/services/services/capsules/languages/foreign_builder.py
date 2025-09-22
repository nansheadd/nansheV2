import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom, AtomContentType
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from openai import OpenAI
from app.core.config import settings
from app.models.user.user_model import User
from app.services.atom_service import AtomService
from app.core import ai_service

logger = logging.getLogger(__name__)

class ForeignBuilder(BaseCapsuleBuilder):
    """
    Builder spécialisé pour les langues, implémentant toutes les méthodes requises.
    """

    def __init__(
        self,
        db: Session,
        capsule: Capsule,
        user: User,
        *,
        source_material: Optional[dict] = None,
    ):
        """
        Constructeur qui accepte db et capsule et les passe au parent.
        """
        super().__init__(db=db, capsule=capsule, user=user, source_material=source_material)
        self.atom_service = AtomService(
            db=db,
            user=user,
            capsule=capsule,
            source_material=source_material,
        )
        try:
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            self.openai_client = None
            logger.error(f"❌ Erreur de configuration OpenAI dans ForeignBuilder: {e}")

    def generate_learning_plan(self, db: Session, capsule: Capsule) -> dict | None:
        """
        Surcharge la génération de plan pour utiliser un prompt spécialisé.
        """
        logger.info("====== ✅ GÉNÉRATION DE PLAN SPÉCIALISÉE (LANGUES) ✅ ======")
        inspirational_examples = self._find_inspirational_examples(db, capsule.domain, capsule.area)
        
        if not self.openai_client: return None
        
        language = capsule.main_skill
        system_prompt = (
            "Tu es un polyglotte et un ingénieur pédagogique. Crée un plan d'apprentissage JSON pour une langue étrangère. "
            "Le plan doit être complet, progressif (A1 à C1), et contenir entre 16 et 25 'levels' (compétences majeures). "
            "Chaque 'level' contient des 'chapters' (leçons spécifiques)."
        )
        user_prompt = f"Crée un plan de cours exceptionnel pour apprendre le {language}."

        if inspirational_examples:
            examples_str = "\n\n---\n\n".join(
                f"Exemple pour '{ex['main_skill']}':\n{json.dumps(ex['plan'], indent=2, ensure_ascii=False)}"
                for ex in inspirational_examples
            )
            user_prompt += (
                f"\n\nInspire-toi de la structure de ces plans pour créer un plan "
                f"entièrement nouveau et adapté pour le {language}.\n\n{examples_str}"
            )

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-5-mini-2025-08-07",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Erreur API OpenAI dans ForeignBuilder : {e}")
            return None

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
            logger.error("Erreur lors de la génération du plan contextualisé pour la capsule de langue : %s", exc, exc_info=True)
            return None

    # === IMPLÉMENTATION OBLIGATOIRE N°1 ===
    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        """
        Définit les "recettes" pour les leçons de langue.
        """
        title = molecule.title.lower()
        if any(keyword in title for keyword in ["hiragana", "katakana", "alphabet", "écriture"]):
            return [{"type": AtomContentType.LESSON}, {"type": AtomContentType.CHARACTER}, {"type": AtomContentType.QUIZ}]
        if any(keyword in title for keyword in ["grammaire", "particules", "verbes", "conjugaison"]):
             return [{"type": AtomContentType.LESSON}, {"type": AtomContentType.GRAMMAR}, {"type": AtomContentType.EXERCISE}]
        if any(keyword in title for keyword in ["conversation", "dialogue", "salutations"]):
            return [{"type": AtomContentType.LESSON}, {"type": AtomContentType.VOCABULARY}, {"type": AtomContentType.DIALOGUE}]
        return [{"type": AtomContentType.LESSON}, {"type": AtomContentType.VOCABULARY}, {"type": AtomContentType.QUIZ}]

    # === IMPLÉMENTATION OBLIGATOIRE N°2 ===
    def _build_atom_content(
        self,
        atom_type: AtomContentType,
        molecule: Molecule,
        context_atoms: List[Atom],
        difficulty: str | None = None,
    ) -> Dict[str, Any] | None:
        """
        "Usine" de fabrication du contenu pour chaque type d'atome de langue.
        """
        if not self.openai_client:
            logger.error("Le client OpenAI n'est pas initialisé dans le ForeignBuilder.")
            return None

        if atom_type == AtomContentType.LESSON:
            system_prompt = "Tu es un professeur de langues. Rédige une leçon claire en Markdown. Réponds UNIQUEMENT avec un JSON: {\"text\": \"...\"}."
            user_prompt = f"Rédige une leçon sur '{molecule.title}' pour un cours de {self.capsule.main_skill}."
            return self._call_openai_for_json(user_prompt, system_prompt)

        if atom_type == AtomContentType.VOCABULARY:
            system_prompt = "Tu es un lexicographe. Génère 10 mots de vocabulaire. Réponds UNIQUEMENT avec un JSON: {\"items\": [{\"word\": \"...\", \"reading\": \"...\", \"meaning\": \"...\"}]}."
            user_prompt = f"Génère le vocabulaire essentiel pour la leçon '{molecule.title}'."
            return self._call_openai_for_json(user_prompt, system_prompt)

        if self.atom_service:
            generated = self.atom_service.create_atom_content(atom_type, molecule, context_atoms, difficulty=difficulty)
            if generated:
                return generated

        logger.warning(f"Aucun fabricant n'est implémenté pour le type d'atome '{atom_type.name}'.")
        return None

    def _call_openai_for_json(self, user_prompt: str, system_prompt: str) -> Dict[str, Any] | None:
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-5-mini-2025-08-07",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Erreur lors de l'appel OpenAI pour obtenir du JSON : {e}")
            return None
