# Fichier: ./app/services/services/capsules/base_builder.py

import logging
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import settings
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom, AtomContentType # <-- NOUVEL IMPORT
from app.models.analytics.vector_store_model import VectorStore
from app.models.capsule.language_roadmap_model import LanguageRoadmap # <-- Importer le bon modèle

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
    def __init__(
        self,
        db: Session,
        capsule: Capsule,
        user: User,
        *,
        source_material: Optional[dict] = None,
    ):
        """
        Initialise le builder avec la session de base de données et la capsule cible.
        """
        self.db = db
        self.capsule = capsule
        self.user = user
        self.source_material: Optional[dict] = source_material or None


    def get_details(self, db: Session, user, capsule: Capsule, **kwargs) -> dict:
        logger.info(f"--> [BASE BUILDER] get_details appelé pour la capsule '{capsule.title}'.")
        return {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _coerce_atom_type(self, value: Any) -> AtomContentType:
        if isinstance(value, AtomContentType):
            return value
        if isinstance(value, str):
            try:
                return AtomContentType(value)
            except ValueError:
                return AtomContentType(value.lower())
        if isinstance(value, dict) and "type" in value:
            return self._coerce_atom_type(value["type"])
        raise ValueError(f"Unsupported atom content type: {value!r}")

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
        if self.source_material:
            logger.info("--> [BASE BUILDER] Génération contextualisée à partir d'une ressource fournie.")
            plan_from_source = self._generate_plan_from_source(db, capsule, self.source_material)
            if plan_from_source:
                return plan_from_source
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

    def _generate_plan_from_source(
        self,
        db: Session,
        capsule: Capsule,
        source_material: dict,
    ) -> dict | None:
        """Point d'extension pour générer un plan à partir d'une ressource externe (PDF, etc.)."""
        return None

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

    def _find_inspirational_examples(self, db: Session, domain: str, area: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Trouve des plans d'apprentissage existants pour servir d'exemples (RAG).
        CORRIGÉ: Interroge maintenant la table LanguageRoadmap.
        """
        logger.info(f"  [RAG] Recherche de {limit} exemples pour {domain}/{area}...")

        # --- CORRECTION ---
        # On interroge LanguageRoadmap et on joint Capsule pour filtrer
        query = (
            db.query(LanguageRoadmap, Capsule)
            .join(Capsule, LanguageRoadmap.capsule_id == Capsule.id)
            .filter(
                Capsule.domain == domain,
                Capsule.area == area,
                LanguageRoadmap.roadmap_data.isnot(None)
            )
            .limit(limit)
            .all()
        )

        examples = []
        for roadmap, capsule in query:
            examples.append({
                "main_skill": capsule.main_skill,
                "plan": roadmap.roadmap_data  # On utilise les données de la roadmap
            })
        
        return examples
    
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
                model="gpt-5-mini-2025-08-07",
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
        recipe = self._get_molecule_recipe(molecule)
        if not recipe:
            logger.warning(f"Aucune recette trouvée pour la molécule '{molecule.title}'.")
            return []

        logger.info(f"Construction de '{molecule.title}' avec la recette : {[item['type'].name for item in recipe]}")
        existing_atoms = sorted(molecule.atoms, key=lambda a: (a.order or 0, a.id))
        core_atoms = [atom for atom in existing_atoms if not getattr(atom, "is_bonus", False)]
        bonus_atoms = [atom for atom in existing_atoms if getattr(atom, "is_bonus", False)]

        # --- Déduplication des anciens atomes (une occurrence par type) ---
        duplicates: list[Atom] = []
        bucket_map: Dict[AtomContentType, list[Atom]] = {}
        for atom in core_atoms:
            bucket = bucket_map.setdefault(self._coerce_atom_type(atom.content_type), [])
            bucket.append(atom)
        for bucket in bucket_map.values():
            if len(bucket) > 1:
                bucket.sort(key=lambda a: a.id or 0)
                duplicates.extend(bucket[1:])
        for duplicate in duplicates:
            logger.info(
                "[BASE BUILDER] Suppression de l'atome dupliqué %s (%s) sur '%s'",
                duplicate.id,
                duplicate.content_type,
                molecule.title,
            )
            self.db.delete(duplicate)
        if duplicates:
            self.db.flush()
            molecule = self.db.get(Molecule, molecule.id)
            existing_atoms = sorted(molecule.atoms, key=lambda a: (a.order or 0, a.id))
            core_atoms = [atom for atom in existing_atoms if not getattr(atom, "is_bonus", False)]
            bonus_atoms = [atom for atom in existing_atoms if getattr(atom, "is_bonus", False)]

        atoms_by_type: dict[AtomContentType, list[Atom]] = {}
        for atom in core_atoms:
            atoms_by_type.setdefault(self._coerce_atom_type(atom.content_type), []).append(atom)

        ordered_atoms: list[Atom] = []

        for atom_info in recipe:
            atom_type: AtomContentType = self._coerce_atom_type(atom_info["type"])
            atom_title = atom_info.get("title", "...")
            atom_difficulty = atom_info.get("difficulty")

            reuse_bucket = atoms_by_type.get(atom_type) or []
            if reuse_bucket:
                atom = reuse_bucket.pop(0)
                if atom_difficulty and atom.difficulty != atom_difficulty:
                    atom.difficulty = atom_difficulty
                ordered_atoms.append(atom)
                continue

            content = self._build_atom_content(
                atom_type,
                molecule,
                ordered_atoms,
                difficulty=atom_difficulty,
            )

            if content:
                new_atom = Atom(
                    title=atom_title,
                    order=len(ordered_atoms) + 1,
                    content_type=atom_type,
                    content=content,
                    difficulty=atom_difficulty,
                    molecule_id=molecule.id,
                )
                self.db.add(new_atom)
                self.db.flush([new_atom])
                ordered_atoms.append(new_atom)

        for remaining in atoms_by_type.values():
            ordered_atoms.extend(remaining)

        ordered_atoms.extend(bonus_atoms)

        for index, atom in enumerate(ordered_atoms, start=1):
            if atom.order != index:
                atom.order = index

        self.db.flush()
        return ordered_atoms

    def _resequence_atom_orders(self, molecule: Molecule) -> List[Atom]:
        atoms = sorted(molecule.atoms, key=lambda a: (a.order or 0, a.id))
        for index, atom in enumerate(atoms, start=1):
            if atom.order != index:
                atom.order = index
        self.db.flush()
        return atoms

    def create_bonus_atom(
        self,
        molecule: Molecule,
        *,
        content_type: AtomContentType,
        title: str,
        difficulty: str | None = None,
    ) -> Atom:
        atom_service = getattr(self, "atom_service", None)
        if atom_service is None:
            raise NotImplementedError("This builder does not support bonus atom generation.")

        existing_atoms = sorted(molecule.atoms, key=lambda a: (a.order or 0, a.id))
        context_atoms = [atom for atom in existing_atoms if not getattr(atom, "is_bonus", False)]
        content = atom_service.create_atom_content(
            atom_type=content_type,
            molecule=molecule,
            context_atoms=context_atoms,
            difficulty=difficulty,
        )
        if not content:
            raise ValueError("bonus_generation_failed")

        next_order = existing_atoms[-1].order + 1 if existing_atoms else 1
        new_atom = Atom(
            title=title,
            order=next_order,
            content_type=content_type,
            content=content,
            difficulty=difficulty,
            molecule_id=molecule.id,
            is_bonus=True,
        )
        self.db.add(new_atom)
        self.db.flush([new_atom])
        self._resequence_atom_orders(molecule)
        return new_atom

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
    def _build_atom_content(
        self,
        atom_type: AtomContentType,
        molecule: Molecule,
        context_atoms: List[Atom],
        difficulty: str | None = None,
    ) -> Dict[str, Any] | None:
        """
        "Fabrique" le contenu JSON pour un type d'atome spécifique.
        'context_atoms' contient les atomes déjà créés pour cette molécule,
        permettant de passer du contexte à l'IA (ex: vocabulaire pour un dialogue).
        DOIT être implémentée par la classe enfant.
        """
        pass
