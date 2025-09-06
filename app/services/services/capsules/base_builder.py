# Fichier: ./app/services/services/capsules/base_builder.py

import logging
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import settings
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom, AtomContentType # <-- NOUVEL IMPORT
from app.models.analytics.vector_store_model import VectorStore
from app.services.rag_utils import get_embedding

logger = logging.getLogger(__name__)

try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    openai_client = None

class BaseCapsuleBuilder(ABC): # <-- On le transforme en classe abstraite
    """
    Builder de base abstrait. Gère la création de capsules, la génération de plans
    intelligente, et fournit un framework pour la génération de contenu par "recette".
    """

    # ========================================================================
    # SECTION 1 : LOGIQUE EXISTANTE (INCHANGÉE)
    # ========================================================================
    def __init__(self, db: Session, capsule: Capsule):
        """
        Initialise le builder avec la session de base de données et la capsule cible.
        """
        self.db = db
        self.capsule = capsule


    def get_details(self, db: Session, user, capsule: Capsule, **kwargs) -> dict:
        logger.info(f"--> [BASE BUILDER] get_details appelé pour la capsule '{capsule.title}'.")
        return {}

    def create_capsule(self, db: Session, user, title: str, classification: dict):
        logger.info("--> [BASE BUILDER] Création de l'entité Capsule (sans plan)...")
        new_capsule = Capsule(
            title=title,
            domain=classification.get("domain"),
            area=classification.get("area"),
            main_skill=classification.get("main_skill"),
            creator_id=user.id,
            is_public=True
        )
        db.add(new_capsule)
        db.commit()
        db.refresh(new_capsule)
        return new_capsule

    def generate_learning_plan(self, db: Session, capsule: Capsule) -> dict | None:
        logger.info(f"--> [BASE BUILDER] Génération de plan pour '{capsule.title}'...")
        existing_plan = self._find_plan_in_vector_store(db, capsule.main_skill)
        if existing_plan:
            logger.info(f"--> [CACHE] ✅ Plan complet trouvé dans VectorStore. Utilisation directe.")
            return existing_plan

        logger.info(f"--> [CACHE] ❌ Aucun plan trouvé. Lancement de la génération (RAG).")
        inspirational_examples = self._find_inspirational_examples(db, capsule.domain, capsule.area)
        new_plan = self._generate_plan_with_openai(capsule, inspirational_examples)

        if not new_plan:
            return None

        self._save_plan_to_vector_store(db, capsule, new_plan)
        return new_plan

    # --- Méthodes de cache et RAG (inchangées) ---

    def _find_plan_in_vector_store(self, db: Session, skill: str) -> dict | None:
        # ... (code existant inchangé)
        vector_entry = db.query(VectorStore).filter(VectorStore.skill == skill).first()
        if vector_entry and (isinstance(vector_entry.chunk_text, dict) or isinstance(vector_entry.chunk_text, str)):
            if isinstance(vector_entry.chunk_text, str):
                try:
                    data = json.loads(vector_entry.chunk_text)
                    if "levels" in data and "overview" in data:
                        return data
                except (json.JSONDecodeError, TypeError):
                    return None
            elif "levels" in vector_entry.chunk_text and "overview" in vector_entry.chunk_text:
                return vector_entry.chunk_text
        return None

    def _save_plan_to_vector_store(self, db: Session, capsule: Capsule, plan: dict):
        # ... (code existant inchangé)
        logger.info(f"--> [CACHE] Sauvegarde du nouveau plan pour '{capsule.main_skill}' dans VectorStore.")
        plan_json_string = json.dumps(plan, ensure_ascii=False)
        new_vector_entry = VectorStore(
            chunk_text=plan_json_string,
            embedding=get_embedding(capsule.main_skill),
            domain=capsule.domain,
            area=capsule.area,
            skill=capsule.main_skill
        )
        db.add(new_vector_entry)
        db.commit()
        
    def _find_atom_in_vector_store(self, db: Session, capsule: Capsule, molecule: Molecule, content_type: str) -> dict | None:
        # ... (code existant inchangé)
        skill_identifier = molecule.title
        vector_entry = db.query(VectorStore).filter(
            VectorStore.skill == skill_identifier,
            VectorStore.domain == capsule.domain,
            VectorStore.area == capsule.area
        ).first()
        if vector_entry:
            logger.info(f"  [CACHE] ✅ Contenu de type '{content_type}' trouvé pour '{skill_identifier}'.")
            try:
                return json.loads(vector_entry.chunk_text) if isinstance(vector_entry.chunk_text, str) else vector_entry.chunk_text
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def _save_atom_to_vector_store(self, db: Session, capsule: Capsule, molecule: Molecule, content_type: str, content: dict):
        # ... (code existant inchangé)
        skill_identifier = molecule.title
        logger.info(f"  [CACHE] Sauvegarde du contenu '{content_type}' pour '{skill_identifier}'.")
        content_json_string = json.dumps(content, ensure_ascii=False)
        new_vector_entry = VectorStore(
            chunk_text=content_json_string,
            embedding=get_embedding(f"{capsule.main_skill}: {skill_identifier}"),
            domain=capsule.domain,
            area=capsule.area,
            skill=skill_identifier
        )
        db.add(new_vector_entry)

    def _find_inspirational_examples(self, db: Session, domain: str, area: str, limit: int = 3) -> list[dict]:
        # ... (code existant inchangé)
        logger.info(f"  [RAG] Recherche de {limit} exemples pour {domain}/{area}...")
        examples = db.query(Capsule).filter(
            Capsule.domain == domain,
            Capsule.area == area,
            Capsule.learning_plan_json.isnot(None)
        ).limit(limit).all()
        if examples:
            logger.info(f"  [RAG] -> ✅ {len(examples)} exemples trouvés.")
            return [{"main_skill": ex.main_skill, "plan": ex.learning_plan_json} for ex in examples]
        return []

    def _generate_plan_with_openai(self, capsule: Capsule, rag_examples: list[dict]) -> dict | None:
        # ... (code existant inchangé)
        if not openai_client: return None
        system_prompt = (
            "Tu es un expert en ingénierie pédagogique. Ta mission est de créer un plan de cours JSON complet et très détaillé. "
            "Le plan doit contenir entre 16 et 25 niveaux ('levels'). Chaque niveau a un 'level_title' et une liste de 'chapters'. "
            "Chaque chapitre a un 'chapter_title'. Le JSON final doit avoir les clés 'overview' et 'levels'."
        )
        user_prompt = f"Crée un plan de cours complet et détaillé pour apprendre : '{capsule.main_skill}'."
        if rag_examples:
            examples_str = "\n\n".join([f"Exemple pour '{ex['main_skill']}':\n{json.dumps(ex['plan'], indent=2, ensure_ascii=False)}" for ex in rag_examples])
            user_prompt += f"\n\nInspire-toi de la structure et de la qualité de ces excellents plans. NE COPIE PAS le contenu, utilise-les comme modèle de qualité:\n{examples_str}"
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Erreur API OpenAI lors de la génération du plan : {e}")
            return None

    # ========================================================================
    # SECTION 2 : NOUVELLE LOGIQUE DE CONSTRUCTION DE CONTENU
    # ========================================================================

    def get_or_create_hierarchy(self, granule_order: int, molecule_order: int) -> Molecule:
        """
        Assure que la hiérarchie Granule -> Molecule existe en BDD et la retourne.
        """
        # ... (code de la réponse précédente, inchangé)
        granule = self.db.query(Granule).filter_by(
            capsule_id=self.capsule.id, 
            order=granule_order
        ).first()
        if not granule:
            try:
                plan = self.capsule.learning_plan_json or {}
                level_data = plan.get("levels", [])[granule_order - 1]
                granule = Granule(
                    capsule_id=self.capsule.id, 
                    order=granule_order, 
                    title=level_data.get("level_title", f"Niveau {granule_order}")
                )
                self.db.add(granule)
                self.db.flush()
            except IndexError:
                raise ValueError(f"Niveau (Granule) d'ordre {granule_order} non trouvé dans le plan JSON.")
        molecule = self.db.query(Molecule).filter_by(
            granule_id=granule.id, 
            order=molecule_order
        ).first()
        if not molecule:
            try:
                plan = self.capsule.learning_plan_json or {}
                level_data = plan.get("levels", [])[granule_order - 1]
                chapter_data = level_data.get("chapters", [])[molecule_order - 1]
                molecule = Molecule(
                    granule_id=granule.id, 
                    order=molecule_order, 
                    title=chapter_data.get("chapter_title", f"Leçon {molecule_order}")
                )
                self.db.add(molecule)
                self.db.flush()
            except IndexError:
                raise ValueError(f"Chapitre (Molecule) d'ordre {molecule_order} non trouvé.")
        return molecule

    def build_molecule_content(self, molecule: Molecule) -> List[Atom]:
        """
        Orchestre la création de tous les Atoms pour une Molecule donnée en suivant une recette.
        """
        if molecule.atoms:
            logger.info(f"Contenu pour '{molecule.title}' (ID: {molecule.id}) existe déjà. Skip.")
            return molecule.atoms

        recipe = self._get_molecule_recipe(molecule)
        if not recipe:
            logger.warning(f"Aucune recette trouvée pour la molécule '{molecule.title}'.")
            return []

        logger.info(f"Construction de '{molecule.title}' avec la recette : {[item['type'].name for item in recipe]}")
        
        created_atoms = []
        for i, atom_info in enumerate(recipe):
            atom_type = atom_info["type"]
            atom_title = atom_info.get("title", atom_type.value.replace('_', ' ').capitalize())
            
            # Intégration de la logique de cache ici !
            content = self._find_atom_in_vector_store(self.db, self.capsule, molecule, atom_type.name)
            
            if not content:
                # Si non trouvé en cache, on fabrique le contenu
                content = self._build_atom_content(atom_type, molecule, created_atoms)
                if content:
                    # Et on le sauvegarde en cache pour la prochaine fois
                    self._save_atom_to_vector_store(self.db, self.capsule, molecule, atom_type.name, content)
            
            if content:
                new_atom = Atom(
                    title=atom_title,
                    order=i + 1,
                    content_type=atom_type,
                    content=content,
                    molecule_id=molecule.id
                )
                self.db.add(new_atom)
                created_atoms.append(new_atom)
        
        self.db.commit()
        return created_atoms

    # --- Méthodes Abstraites à implémenter par les builders spécifiques ---

    @abstractmethod
    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        """
        Retourne la "recette" (séquence d'atomes) pour une molécule.
        Ex: [{"type": AtomContentType.LESSON}, {"type": AtomContentType.VOCABULARY}]
        DOIT être implémentée par la classe enfant.
        """
        pass

    @abstractmethod
    def _build_atom_content(self, atom_type: AtomContentType, molecule: Molecule, context_atoms: List[Atom]) -> Dict[str, Any] | None:
        """
        "Fabrique" le contenu JSON pour un type d'atome spécifique.
        'context_atoms' contient les atomes déjà créés pour cette molécule,
        permettant de passer du contexte à l'IA (ex: vocabulaire pour un dialogue).
        DOIT être implémentée par la classe enfant.
        """
        pass