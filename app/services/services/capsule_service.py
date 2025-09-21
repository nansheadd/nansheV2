import importlib
import logging
import json
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session, selectinload

from app.models.analytics.vector_store_model import VectorStore
from app.models.capsule.atom_model import Atom, AtomContentType
from app.models.capsule.capsule_model import Capsule, GenerationStatus
from app.models.capsule.granule_model import Granule
from app.models.capsule.language_roadmap_model import (
    LanguageRoadmap,
    LanguageRoadmapLevel,
    LevelSkillTarget,
    LevelFocus,
)
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.utility_models import UserCapsuleEnrollment, UserCapsuleProgress
from app.models.progress.user_atomic_progress import UserAtomProgress
from app.models.progress.user_course_progress_model import UserCourseProgress
from app.models.user.notification_model import NotificationCategory
from app.models.user.user_model import User, SubscriptionStatus
from app.crud import notification_crud
from app.schemas.user import notification_schema
from app.services.rag_utils import get_embedding
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from app.services.services.capsules.languages.foreign_builder import ForeignBuilder
from app.services.services.capsules.others.default_builder import DefaultBuilder
from app.services.services.capsules.programming import ProgrammingBuilder
from app.services.progress_service import TOTAL_XP, BONUS_XP_PER_MOLECULE, calculate_capsule_xp_distribution
from app.crud import badge_crud
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.analytics.feedback_model import ContentFeedback


# --- Configuration ---
logger = logging.getLogger(__name__)

try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")

# ==============================================================================
# SECTION 1: FONCTION D'AIGUILLAGE (Dispatcher)
# ==============================================================================
def _get_builder_for_capsule(db: Session, capsule: Capsule, user: User) -> BaseCapsuleBuilder: # Ajoutez user ici
    domain = capsule.domain
    logger.info(f"Sélection du builder pour le domaine : '{domain}'")

    if domain == "languages":
        return ForeignBuilder(db=db, capsule=capsule, user=user) # Passez user

    if domain == "programming":
        area = (capsule.area or "").lower()
        return ProgrammingBuilder(db=db, capsule=capsule, user=user)

    return DefaultBuilder(db=db, capsule=capsule, user=user)


def get_builder_for_capsule(domain: str, area: str, db: Session, capsule: Capsule) -> BaseCapsuleBuilder:
    """Compatibilité rétro : construit le builder en résolvant l'utilisateur si besoin."""
    user = getattr(capsule, "creator", None)
    if user is None and capsule.creator_id:
        user = db.get(User, capsule.creator_id)
    if user is None:
        raise ValueError("Impossible de déterminer le créateur de la capsule pour sélectionner le builder.")
    return _get_builder_for_capsule(db=db, capsule=capsule, user=user)


# ==============================================================================
# SECTION 2: CLASSE DE SERVICE PRINCIPALE
# ==============================================================================

class CapsuleService:
    """
    Service principal pour orchestrer les opérations liées aux capsules.
    Il utilise un système de "Builders" pour déléguer la logique spécifique à chaque type de capsule.
    """
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self._progress_cache: Dict[int, UserAtomProgress] | None = None
        self._progress_cache_capsule_id: Optional[int] = None
        self._is_superuser = bool(getattr(user, "is_superuser", False))
        self._is_premium = getattr(user, "subscription_status", SubscriptionStatus.FREE) == SubscriptionStatus.PREMIUM

    # ------------------------------------------------------------------
    # Helpers de progression
    # ------------------------------------------------------------------
    def _get_progress_map_for_atom_ids(self, atom_ids: List[int]) -> Dict[int, UserAtomProgress]:
        if not atom_ids:
            return {}
        entries = (
            self.db.query(UserAtomProgress)
            .filter(UserAtomProgress.user_id == self.user.id, UserAtomProgress.atom_id.in_(atom_ids))
            .all()
        )
        return {entry.atom_id: entry for entry in entries}

    def _get_progress_map_for_capsule(self, capsule: Capsule) -> Dict[int, UserAtomProgress]:
        if self._progress_cache_capsule_id == capsule.id and self._progress_cache is not None:
            return self._progress_cache
        atom_ids: List[int] = []
        for granule in capsule.granules:
            for molecule in granule.molecules:
                atom_ids.extend(atom.id for atom in molecule.atoms)
        progress_map = self._get_progress_map_for_atom_ids(atom_ids)
        self._progress_cache = progress_map
        self._progress_cache_capsule_id = capsule.id
        return progress_map

    def _is_molecule_completed(self, molecule: Molecule, progress_map: Optional[Dict[int, UserAtomProgress]] = None) -> bool:
        core_atoms = [atom for atom in molecule.atoms if not getattr(atom, 'is_bonus', False)]
        if not core_atoms:
            return True
        if progress_map is None:
            progress_map = self._get_progress_map_for_atom_ids([atom.id for atom in core_atoms])
        for atom in core_atoms:
            progress = progress_map.get(atom.id)
            if not progress or progress.status != 'completed':
                return False
        return True

    def _compute_molecule_progress_status(
        self,
        molecule: Molecule,
        progress_map: Optional[Dict[int, UserAtomProgress]] = None,
    ) -> str:
        if progress_map is None:
            progress_map = self._get_progress_map_for_atom_ids([atom.id for atom in molecule.atoms])
        if self._is_molecule_completed(molecule, progress_map):
            return 'completed'
        has_attempt = False
        has_failure = False
        for atom in molecule.atoms:
            if getattr(atom, 'is_bonus', False):
                continue
            progress = progress_map.get(atom.id)
            if progress:
                if progress.status == 'failed':
                    has_failure = True
                if progress.attempts > 0:
                    has_attempt = True
        if has_failure:
            return 'failed'
        if has_attempt:
            return 'in_progress'
        return 'not_started'

    def _is_granule_completed(
        self,
        granule: Granule,
        progress_map: Optional[Dict[int, UserAtomProgress]] = None,
    ) -> bool:
        molecules = sorted(granule.molecules, key=lambda m: m.order)
        if not molecules:
            return False
        for molecule in molecules:
            if not self._is_molecule_completed(molecule, progress_map):
                return False
        return True

    def _is_molecule_unlocked(self, molecule: Molecule) -> bool:
        if self._is_superuser:
            return True
        granule = molecule.granule
        if granule.order > 1:
            previous_granule = (
                self.db.query(Granule)
                .filter(Granule.capsule_id == granule.capsule_id, Granule.order == granule.order - 1)
                .first()
            )
            if previous_granule and not self._is_granule_completed(previous_granule):
                return False
        if molecule.order > 1:
            previous_molecule = (
                self.db.query(Molecule)
                .filter(Molecule.granule_id == granule.id, Molecule.order == molecule.order - 1)
                .first()
            )
            if previous_molecule and not self._is_molecule_completed(previous_molecule):
                return False
        return True

    def _ensure_molecule_unlocked(self, molecule: Molecule):
        if self._is_superuser:
            return
        if not self._is_molecule_unlocked(molecule):
            raise HTTPException(status_code=403, detail="molecule_locked")

    def assert_molecule_unlocked(self, molecule: Molecule):
        self._ensure_molecule_unlocked(molecule)

    def _annotate_atoms_with_progress(self, atoms: List[Atom]) -> List[Atom]:
        atoms_sorted = sorted(atoms, key=lambda a: a.order)
        progress_map = self._get_progress_map_for_atom_ids([atom.id for atom in atoms_sorted])
        for atom in atoms_sorted:
            progress = progress_map.get(atom.id)
            progress_status = progress.status if progress else 'not_started'
            setattr(atom, 'progress_status', progress_status)
            setattr(atom, 'is_bonus', bool(getattr(atom, 'is_bonus', False)))
            setattr(atom, 'is_locked', False)
        return atoms_sorted

    def annotate_capsule(self, capsule: Capsule) -> Capsule:
        progress_map = self._get_progress_map_for_capsule(capsule)
        atom_xp_map, molecule_xp_totals = calculate_capsule_xp_distribution(capsule)
        molecule_ids: list[int] = []
        atom_ids: list[int] = list(atom_xp_map.keys())
        seen_atom_ids = set(atom_ids)
        for granule in capsule.granules:
            for molecule in granule.molecules:
                molecule_ids.append(molecule.id)
                for atom in molecule.atoms:
                    if atom.id not in seen_atom_ids:
                        atom_ids.append(atom.id)
                        seen_atom_ids.add(atom.id)

        feedback_entries: list[ContentFeedback] = []
        if molecule_ids or atom_ids:
            target_ids = molecule_ids + atom_ids
            feedback_entries = (
                self.db.query(ContentFeedback)
                .options(selectinload(ContentFeedback.detail))
                .filter(
                    ContentFeedback.user_id == self.user.id,
                    ContentFeedback.content_type.in_(["molecule", "atom"]),
                    ContentFeedback.content_id.in_(target_ids),
                )
                .all()
            )
        molecule_feedback_map = {
            fb.content_id: fb for fb in feedback_entries if fb.content_type == "molecule"
        }
        atom_feedback_map = {
            fb.content_id: fb for fb in feedback_entries if fb.content_type == "atom"
        }
        capsule_progress = (
            self.db.query(UserCapsuleProgress)
            .filter(
                UserCapsuleProgress.user_id == self.user.id,
                UserCapsuleProgress.capsule_id == capsule.id,
            )
            .first()
        )
        capsule_xp = capsule_progress.xp if capsule_progress and capsule_progress.xp else 0
        capsule_bonus_xp = capsule_progress.bonus_xp if capsule_progress and capsule_progress.bonus_xp else 0
        setattr(capsule, "user_xp", capsule_xp)
        setattr(capsule, "user_bonus_xp", capsule_bonus_xp)
        setattr(capsule, "xp_target", TOTAL_XP)
        setattr(capsule, "xp_remaining", max(0, TOTAL_XP - capsule_xp))
        completed_granules: Dict[int, bool] = {}
        granules_sorted = sorted(capsule.granules, key=lambda g: g.order)
        capsule_bonus_total = 0
        capsule_bonus_earned = 0
        for granule in granules_sorted:
            prev_granule_completed = completed_granules.get(granule.order - 1, granule.order == 1)
            granule_locked = (granule.order > 1 and not prev_granule_completed) and not self._is_superuser
            setattr(granule, 'is_locked', granule_locked)
            molecules_sorted = sorted(granule.molecules, key=lambda m: m.order)
            prev_molecule_completed = prev_granule_completed
            molecule_statuses = []
            granule_xp_total = 0
            granule_xp_earned = 0
            granule_bonus_total = 0
            granule_bonus_earned = 0
            for molecule in molecules_sorted:
                completed = self._is_molecule_completed(molecule, progress_map)
                status = self._compute_molecule_progress_status(molecule, progress_map)
                is_locked = (granule_locked or (molecule.order > 1 and not prev_molecule_completed)) and not self._is_superuser
                setattr(molecule, 'is_locked', is_locked)
                setattr(molecule, 'progress_status', status)
                feedback_entry = molecule_feedback_map.get(molecule.id)
                if feedback_entry:
                    detail = feedback_entry.detail
                    setattr(molecule, 'user_feedback_rating', feedback_entry.rating)
                    setattr(molecule, 'user_feedback_reason', detail.reason_code if detail else None)
                    setattr(molecule, 'user_feedback_comment', detail.comment if detail else None)
                else:
                    setattr(molecule, 'user_feedback_rating', None)
                    setattr(molecule, 'user_feedback_reason', None)
                    setattr(molecule, 'user_feedback_comment', None)
                molecule_statuses.append(status)
                molecule_total_xp = molecule_xp_totals.get(molecule.id, 0)
                molecule_earned_xp = 0
                molecule_bonus_total = 0
                molecule_bonus_earned = 0
                for atom in molecule.atoms:
                    atom_xp = atom_xp_map.get(atom.id, 0)
                    setattr(atom, 'xp_value', atom_xp)
                    setattr(atom, 'capsule_id', capsule.id)
                    setattr(atom, 'molecule_id', molecule.id)
                    atom_progress_entry = progress_map.get(atom.id)
                    if getattr(atom, 'is_bonus', False):
                        molecule_bonus_total += atom_xp
                        if atom_progress_entry and atom_progress_entry.xp_awarded:
                            molecule_bonus_earned += atom_xp
                    else:
                        if atom_progress_entry and atom_progress_entry.xp_awarded:
                            molecule_earned_xp += atom_xp
                    atom_feedback_entry = atom_feedback_map.get(atom.id)
                    if atom_feedback_entry:
                        atom_detail = atom_feedback_entry.detail
                        setattr(atom, 'user_feedback_rating', atom_feedback_entry.rating)
                        setattr(atom, 'user_feedback_reason', atom_detail.reason_code if atom_detail else None)
                        setattr(atom, 'user_feedback_comment', atom_detail.comment if atom_detail else None)
                    else:
                        setattr(atom, 'user_feedback_rating', None)
                        setattr(atom, 'user_feedback_reason', None)
                        setattr(atom, 'user_feedback_comment', None)
                setattr(molecule, 'xp_total', molecule_total_xp)
                setattr(molecule, 'xp_earned', molecule_earned_xp)
                setattr(molecule, 'xp_percent', min(1.0, molecule_earned_xp / molecule_total_xp) if molecule_total_xp else 0.0)
                setattr(molecule, 'bonus_xp_total', molecule_bonus_total)
                setattr(molecule, 'bonus_xp_earned', molecule_bonus_earned)
                granule_xp_total += molecule_total_xp
                granule_xp_earned += molecule_earned_xp
                granule_bonus_total += molecule_bonus_total
                granule_bonus_earned += molecule_bonus_earned
                capsule_bonus_total += molecule_bonus_total
                capsule_bonus_earned += molecule_bonus_earned
                prev_molecule_completed = completed
            granule_completed = all(self._is_molecule_completed(m, progress_map) for m in molecules_sorted) if molecules_sorted else False
            completed_granules[granule.order] = granule_completed
            if granule_completed:
                progress_state = 'completed'
            elif any(status != 'not_started' for status in molecule_statuses):
                progress_state = 'in_progress'
            else:
                progress_state = 'not_started'
            setattr(granule, 'progress_status', progress_state)
            setattr(granule, 'xp_total', granule_xp_total)
            setattr(granule, 'xp_earned', granule_xp_earned)
            setattr(granule, 'xp_percent', min(1.0, granule_xp_earned / granule_xp_total) if granule_xp_total else 0.0)
            setattr(granule, 'bonus_xp_total', granule_bonus_total)
            setattr(granule, 'bonus_xp_earned', granule_bonus_earned)

        setattr(capsule, 'bonus_xp_total', capsule_bonus_total)
        setattr(capsule, 'bonus_xp_earned', capsule_bonus_earned)
        setattr(capsule, 'bonus_xp_remaining', max(0, capsule_bonus_total - capsule_bonus_earned))
        setattr(capsule, 'xp_percent', min(1.0, capsule_xp / TOTAL_XP) if TOTAL_XP else 0.0)
        return capsule

    def completion_snapshot(self, molecule: Molecule) -> Dict[str, bool | str]:
        capsule = molecule.granule.capsule
        progress_map = self._get_progress_map_for_capsule(capsule)
        molecule_completed = self._is_molecule_completed(molecule, progress_map)
        granule_completed = self._is_granule_completed(molecule.granule, progress_map)
        progress_status = self._compute_molecule_progress_status(molecule, progress_map)

        # Next molecule/granule unlock detection
        next_molecule = (
            self.db.query(Molecule)
            .filter(Molecule.granule_id == molecule.granule_id, Molecule.order == molecule.order + 1)
            .first()
        )
        next_molecule_unlocked = False
        if next_molecule:
            next_molecule_unlocked = self._is_molecule_unlocked(next_molecule)

        next_granule_unlocked = granule_completed

        return {
            "progress_status": progress_status,
            "molecule_completed": molecule_completed,
            "granule_completed": granule_completed,
            "next_molecule_unlocked": next_molecule_unlocked,
            "next_granule_unlocked": next_granule_unlocked,
        }

    # ------------------------------------------------------------------
    # Notifications utilitaires
    # ------------------------------------------------------------------
    def _notify(self, *, title: str, message: str, link: Optional[str] = None):
        """Crée une notification capsule pour l'utilisateur courant."""
        try:
            notification_crud.create_notification(
                self.db,
                notification_schema.NotificationCreate(
                    user_id=self.user.id,
                    title=title,
                    message=message,
                    category=NotificationCategory.CAPSULE,
                    link=link,
                ),
            )
        except Exception as exc:  # ne jamais bloquer la génération pour un souci de notif
            logger.error("[NOTIFY] Échec de création de notification: %s", exc, exc_info=True)
            try:
                self.db.rollback()
            except Exception:  # defensive: rollback could fail if connection closed
                pass

    def _notify_enrolled_users(
        self,
        capsule: Capsule,
        *,
        title: str,
        message: str,
        link: Optional[str] = None,
        exclude_user_ids: Optional[set[int]] = None,
    ):
        """Diffuse une notification à tous les inscrits d'une capsule."""
        try:
            enrollments = (
                self.db.query(UserCapsuleEnrollment)
                .filter(UserCapsuleEnrollment.capsule_id == capsule.id)
                .all()
            )
            for enrollment in enrollments:
                if exclude_user_ids and enrollment.user_id in exclude_user_ids:
                    continue
                notification_crud.create_notification(
                    self.db,
                    notification_schema.NotificationCreate(
                        user_id=enrollment.user_id,
                        title=title,
                        message=message,
                        category=NotificationCategory.CAPSULE,
                        link=link,
                    ),
                )
        except Exception as exc:
            logger.error("[NOTIFY] Diffusion bonus échouée: %s", exc, exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass

    def create_capsule(self, background_tasks: BackgroundTasks, classification_result: dict) -> Capsule:
        logger.info("\n--- [SERVICE] Début du processus de création de capsule ---")
        main_skill = classification_result.get('main_skill')
        if not main_skill:
            raise ValueError("La classification n'a pas pu déterminer la compétence principale.")

        existing_capsule = self.db.query(Capsule).filter(
            Capsule.main_skill == main_skill,
            Capsule.creator_id == self.user.id
        ).first()
        
        if existing_capsule:
            logger.info(f"--- [SERVICE] Une capsule pour '{main_skill}' existe déjà (ID: {existing_capsule.id}).")
            existing_roadmap = self.db.query(LanguageRoadmap).filter_by(capsule_id=existing_capsule.id, user_id=self.user.id).first()
            if not existing_roadmap and existing_capsule.generation_status != 'pending':
                logger.info("--- [SERVICE] La roadmap est manquante, relance de la tâche de génération. ---")
                background_tasks.add_task(self.generate_and_save_plan, existing_capsule.id, self.user.id)
            return existing_capsule

        logger.info(f"--- [SERVICE] Aucune capsule existante pour '{main_skill}'. Création...")
        new_capsule = Capsule(
            title=main_skill.capitalize(),
            main_skill=main_skill,
            domain=classification_result.get("domain", "others"),
            area=classification_result.get("area", "default"),
            creator_id=self.user.id
        )
        self.db.add(new_capsule)
        self.db.commit()
        self.db.refresh(new_capsule)
        
        logger.info(f"--- [SERVICE] Capsule ID {new_capsule.id} créée. Lancement de la génération du plan en fond. ---")
        # Badges de création
        try:
            badge_crud.award_badge(self.db, self.user.id, "artisan-premiere-capsule")
            total_created = self.db.query(Capsule).filter(Capsule.creator_id == self.user.id).count()
            if total_created >= 5:
                badge_crud.award_badge(self.db, self.user.id, "artisan-cinq-capsules")
            # Badges uniques par type: premier dans le domaine/area pour CET utilisateur
            domain_count = self.db.query(Capsule).filter(Capsule.creator_id == self.user.id, Capsule.domain == new_capsule.domain).count()
            if domain_count == 1:
                badge_crud.award_pioneer_for_domain(self.db, self.user.id, new_capsule.domain)
            area_count = self.db.query(Capsule).filter(
                Capsule.creator_id == self.user.id,
                Capsule.domain == new_capsule.domain,
                Capsule.area == new_capsule.area,
            ).count()
            if area_count == 1:
                badge_crud.award_pioneer_for_area(self.db, self.user.id, new_capsule.domain, new_capsule.area)
        except Exception:
            pass

        background_tasks.add_task(self.generate_and_save_plan, new_capsule.id, self.user.id)
        return new_capsule
    

    def prepare_session_for_level(self, capsule: Capsule, granule_order: int, molecule_order: int) -> List[Atom]:
        """
        Prépare et génère le contenu d'une molécule (leçon) spécifique si nécessaire.
        """
        # On utilise le dispatcher pour obtenir le bon builder
        builder = _get_builder_for_capsule(self.db, capsule, self.user)
        
        # 1. S'assurer que la hiérarchie DB (Granule -> Molecule) existe
        molecule = builder.get_or_create_hierarchy(granule_order, molecule_order)
        self._ensure_molecule_unlocked(molecule)

        # Réutilise la logique principale
        return self.get_or_generate_atoms_for_molecule(molecule.id)
    

    def create_capsule_from_classification(self, classification_data: dict) -> Capsule:
        """
        Version corrigée qui utilise la méthode generate_learning_plan du builder
        et crée la hiérarchie de la capsule.
        """
        topic = classification_data.get("main_skill", "Sujet inconnu")
        logger.info(f"\n--- [SERVICE] Création de capsule à partir de la classification pour: '{topic}' ---")
        
        new_capsule = Capsule(
            title=topic.capitalize(),
            main_skill=topic,
            domain=classification_data.get("domain", "others"),
            area=classification_data.get("area", "generic"),
            creator_id=self.user.id,
            generation_status=GenerationStatus.PENDING
        )
        self.db.add(new_capsule)
        self.db.commit()
        self.db.refresh(new_capsule)
        logger.info(f"--- [SERVICE] Capsule ID {new_capsule.id} créée. ---")

        # Inscrire automatiquement le créateur et initialiser sa progression
        self.db.add(UserCapsuleEnrollment(user_id=self.user.id, capsule_id=new_capsule.id))
        self.db.add(UserCourseProgress(user_id=self.user.id, capsule_id=new_capsule.id))
        self.db.commit()
        logger.info(f"--- [SERVICE] Utilisateur {self.user.id} inscrit à la capsule {new_capsule.id}. ---")

        try:
            badge_crud.award_badge(self.db, self.user.id, "artisan-premiere-capsule")
            total_created = self.db.query(Capsule).filter(Capsule.creator_id == self.user.id).count()
            if total_created >= 5:
                badge_crud.award_badge(self.db, self.user.id, "artisan-cinq-capsules")
            # Badges uniques par type (première capsule de l'utilisateur dans domaine/area)
            domain_count = self.db.query(Capsule).filter(Capsule.creator_id == self.user.id, Capsule.domain == new_capsule.domain).count()
            if domain_count == 1:
                badge_crud.award_pioneer_for_domain(self.db, self.user.id, new_capsule.domain)
            area_count = self.db.query(Capsule).filter(
                Capsule.creator_id == self.user.id,
                Capsule.domain == new_capsule.domain,
                Capsule.area == new_capsule.area,
            ).count()
            if area_count == 1:
                badge_crud.award_pioneer_for_area(self.db, self.user.id, new_capsule.domain, new_capsule.area)
        except Exception:
            pass

        builder = _get_builder_for_capsule(self.db, new_capsule, self.user)
        
        # --- CORRECTION 1 : Appeler la bonne méthode ---
        # On appelle la méthode de la classe de base qui génère le plan JSON.
        logger.info(f"--- [SERVICE] Lancement de generate_learning_plan() pour la capsule {new_capsule.id}. ---")
        plan_json = builder.generate_learning_plan(db=self.db, capsule=new_capsule)

        if not plan_json:
            new_capsule.generation_status = GenerationStatus.FAILED
            self.db.commit()
            logger.error(f"--- [SERVICE] Échec de la génération du plan pour la capsule {new_capsule.id}.")
            # Vous pourriez vouloir retourner une erreur ici, mais pour l'instant on continue.
            return new_capsule

        # --- CORRECTION 2 : Sauvegarder le plan et créer la structure ---
        # On sauvegarde le plan JSON dans l'objet capsule.
        new_capsule.learning_plan_json = plan_json
        
        # On parcourt le plan pour créer les "coquilles vides" des Granules et Molécules.
        for g_order, level_data in enumerate(plan_json.get("levels", [])):
            new_granule = Granule(
                title=level_data.get("level_title", f"Niveau {g_order + 1}"),
                order=g_order + 1,
                capsule_id=new_capsule.id
            )
            self.db.add(new_granule)
            self.db.flush() # Nécessaire pour obtenir l'ID du granule

            for m_order, chapter_data in enumerate(level_data.get("chapters", [])):
                new_molecule = Molecule(
                    title=chapter_data.get("chapter_title", f"Leçon {m_order + 1}"),
                    order=m_order + 1,
                    granule_id=new_granule.id
                )
                self.db.add(new_molecule)
                
        new_capsule.generation_status = GenerationStatus.COMPLETED
        self.db.commit()
        self.db.refresh(new_capsule)

        # --- CORRECTION 3 : La logique de génération du contenu initial reste la même ---
        logger.info(f"--- [SERVICE] Génération du contenu initial pour la première molécule. ---")
        first_molecule = self.db.query(Molecule).join(Granule).filter(
            Granule.capsule_id == new_capsule.id
        ).order_by(Granule.order, Molecule.order).first()

        if first_molecule:
            builder.build_molecule_content(first_molecule)
            self.db.commit()
        else:
            logger.warning(f"--- [SERVICE] Le plan généré pour la capsule {new_capsule.id} est vide.")

        self._notify(
            title=f"Capsule prête : {new_capsule.title}",
            message="Le plan d'apprentissage est disponible. Tu peux lancer la première leçon !",
            link=f"/capsule/{new_capsule.domain}/{new_capsule.area}/{new_capsule.id}/plan",
        )

        return new_capsule
    

    def generate_next_molecule_content(self, completed_molecule_id: int) -> List[Atom]:
        """
        Génère le contenu pour la molécule suivante et le retourne (logique JIT),
        SANS utiliser de module CRUD.
        """
        logger.info(f"--- [SERVICE] Requête JIT pour la molécule suivant {completed_molecule_id}. ---")
        
        completed_molecule = self.db.query(Molecule).get(completed_molecule_id)
        if not completed_molecule:
            return []

        self._progress_cache = None
        self._progress_cache_capsule_id = None

        # === CORRECTION : Requête directe pour trouver la molécule suivante ===
        next_molecule = self.db.query(Molecule).filter(
            Molecule.granule_id == completed_molecule.granule_id,
            Molecule.order == completed_molecule.order + 1
        ).first()

        if not next_molecule:
            logger.info("--- [SERVICE] Fin du granule ou de la capsule, pas de molécule suivante. ---")
            return []

        self._ensure_molecule_unlocked(next_molecule)

        if next_molecule.atoms:
            logger.info(f"--- [SERVICE] Les atomes pour la molécule {next_molecule.id} existent déjà. On les retourne. ---")
            atoms_existing = sorted(next_molecule.atoms, key=lambda a: a.order)
            return self._annotate_atoms_with_progress(atoms_existing)

        if getattr(next_molecule, "generation_status", None) == GenerationStatus.PENDING:
            logger.info("--- [SERVICE] Génération déjà en cours pour cette molécule. ---")
            raise HTTPException(status_code=202, detail="generation_in_progress")

        next_molecule.generation_status = GenerationStatus.PENDING
        self.db.commit()

        builder = _get_builder_for_capsule(self.db, next_molecule.granule.capsule, self.user)
        
        logger.info(f"--- [SERVICE] Génération des atomes pour la molécule {next_molecule.id}... ---")
        try:
            atoms = builder.build_molecule_content(next_molecule)
            self.db.commit()
        except Exception as exc:
            logger.error("Echec de génération pour la molécule %s : %s", next_molecule.id, exc, exc_info=True)
            next_molecule.generation_status = GenerationStatus.FAILED
            self.db.commit()
            raise
        else:
            next_molecule.generation_status = GenerationStatus.COMPLETED
            self.db.commit()

        if atoms:
            self._notify(
                title="Nouvelle leçon débloquée",
                message=f"La leçon '{next_molecule.title}' est prête dans la capsule {next_molecule.granule.capsule.title}.",
                link=f"/capsule/{next_molecule.granule.capsule.domain}/{next_molecule.granule.capsule.area}/{next_molecule.granule.capsule.id}/plan",
            )
        
        return atoms
    

    def get_or_generate_atoms_for_molecule(self, molecule_id: int) -> List[Atom]:
        """
        Récupère les atomes d'une molécule. S'ils n'existent pas, les génère.
        """
        logger.info(f"--- [SERVICE] Demande d'atomes pour la molécule ID: {molecule_id} ---")
        
        molecule = self.db.query(Molecule).get(molecule_id)
        if not molecule:
            logger.error(f"--- [SERVICE] Molécule ID {molecule_id} non trouvée.")
            return [] # Ou lever une HTTPException

        self._progress_cache = None
        self._progress_cache_capsule_id = None

        self._ensure_molecule_unlocked(molecule)

        capsule = molecule.granule.capsule
        builder = _get_builder_for_capsule(self.db, capsule, self.user)

        # 1. Vérifier si les atomes existent déjà (cache BDD)
        if molecule.atoms:
            logger.info(f"--- [SERVICE] Atomes trouvés en BDD pour la molécule '{molecule.title}'. Vérification des contenus manquants. ---")
            existing_atoms = sorted(molecule.atoms, key=lambda a: a.order)
            existing_types = {atom.content_type for atom in existing_atoms}
            expected_types = [item["type"] for item in builder._get_molecule_recipe(molecule)]
            missing_types = [atom_type for atom_type in expected_types if atom_type not in existing_types]

            if missing_types:
                logger.info(
                    "--- [SERVICE] Types d'atomes manquants détectés (%s). Lancement d'une complétion. ---",
                    ", ".join(t.value for t in missing_types),
                )
                try:
                    builder.build_molecule_content(molecule)
                    self.db.commit()
                except Exception as exc:
                    logger.error(
                        "Echec lors de la complétion d'atomes pour la molécule %s : %s",
                        molecule.id,
                        exc,
                        exc_info=True,
                    )
                    raise
                existing_atoms = sorted(molecule.atoms, key=lambda a: a.order)

            annotated_atoms = self._annotate_atoms_with_progress(existing_atoms)
            atom_xp_map, _ = calculate_capsule_xp_distribution(capsule)
            for atom in annotated_atoms:
                setattr(atom, 'xp_value', atom_xp_map.get(atom.id, 0))
            return annotated_atoms

        # 2. Si non, on les génère
        logger.info(f"--- [SERVICE] Aucun atome trouvé. Lancement de la génération pour '{molecule.title}'.")

        if getattr(molecule, "generation_status", None) == GenerationStatus.PENDING:
            logger.info("--- [SERVICE] Génération déjà en cours pour cette molécule. ---")
            raise HTTPException(status_code=202, detail="generation_in_progress")

        molecule.generation_status = GenerationStatus.PENDING
        self.db.commit()

        try:
            atoms = builder.build_molecule_content(molecule)
            self.db.commit()
        except Exception as exc:
            logger.error("Echec de génération d'atomes pour la molécule %s : %s", molecule.id, exc, exc_info=True)
            molecule.generation_status = GenerationStatus.FAILED
            self.db.commit()
            raise
        else:
            self.db.refresh(molecule)
            molecule.generation_status = GenerationStatus.COMPLETED
            self.db.commit()

        if atoms:
            self._notify(
                title="Contenu généré",
                message=f"Les ressources de la leçon '{molecule.title}' sont disponibles.",
                link=f"/capsule/{capsule.domain}/{capsule.area}/{capsule.id}/plan",
            )

        atoms_sorted = sorted(molecule.atoms, key=lambda a: a.order)
        annotated_atoms = self._annotate_atoms_with_progress(atoms_sorted)
        atom_xp_map, _ = calculate_capsule_xp_distribution(capsule)
        for atom in annotated_atoms:
            setattr(atom, 'xp_value', atom_xp_map.get(atom.id, 0))
            setattr(atom, 'capsule_id', capsule.id)
            setattr(atom, 'molecule_id', molecule.id)
        return annotated_atoms

    def generate_bonus_atom(
        self,
        molecule_id: int,
        *,
        kind: str,
        difficulty: Optional[str] = None,
        title: Optional[str] = None,
    ) -> List[Atom]:
        molecule = self.db.query(Molecule).get(molecule_id)
        if not molecule:
            raise HTTPException(status_code=404, detail="molecule_not_found")

        if not (self._is_superuser or self._is_premium):
            raise HTTPException(status_code=403, detail="premium_required")

        self._ensure_molecule_unlocked(molecule)

        capsule = molecule.granule.capsule
        builder = _get_builder_for_capsule(self.db, capsule, self.user)

        kind_normalized = (kind or "").strip().lower()
        kind_map = {
            "lesson": AtomContentType.LESSON,
            "theory": AtomContentType.LESSON,
            "exercise": AtomContentType.QUIZ,
            "quiz": AtomContentType.QUIZ,
        }
        content_type = kind_map.get(kind_normalized)
        if content_type is None:
            raise HTTPException(status_code=422, detail="invalid_bonus_kind")

        existing_bonus = [
            atom
            for atom in molecule.atoms
            if getattr(atom, "is_bonus", False) and atom.content_type == content_type
        ]
        default_title = (
            f"Bonus théorie #{len(existing_bonus) + 1}" if content_type == AtomContentType.LESSON else f"Bonus exercice #{len(existing_bonus) + 1}"
        )
        resolved_title = title.strip() if title else default_title
        resolved_difficulty = difficulty or ("bonus" if content_type == AtomContentType.QUIZ else None)

        try:
            builder.create_bonus_atom(
                molecule=molecule,
                content_type=content_type,
                title=resolved_title,
                difficulty=resolved_difficulty,
            )
            molecule.generation_status = GenerationStatus.COMPLETED
            self.db.commit()
        except HTTPException:
            raise
        except NotImplementedError as exc:
            raise HTTPException(status_code=400, detail="bonus_not_supported") from exc
        except Exception as exc:
            logger.error("[BONUS] Echec génération bonus: %s", exc, exc_info=True)
            self.db.rollback()
            raise HTTPException(status_code=500, detail="bonus_generation_failed") from exc

        # rafraîchir les atomes et le cache progression
        self._progress_cache = None
        self._progress_cache_capsule_id = None
        self.db.refresh(molecule)

        atoms_sorted = sorted(molecule.atoms, key=lambda a: a.order)
        annotated_atoms = self._annotate_atoms_with_progress(atoms_sorted)
        atom_xp_map, _ = calculate_capsule_xp_distribution(capsule)
        for atom in annotated_atoms:
            setattr(atom, 'xp_value', atom_xp_map.get(atom.id, 0))
            setattr(atom, 'capsule_id', capsule.id)
            setattr(atom, 'molecule_id', molecule.id)

        link = f"/capsule/{capsule.domain}/{capsule.area}/{capsule.id}/plan?molecule={molecule.id}"
        message = f"Une nouvelle ressource bonus est disponible dans '{molecule.title}'."
        self._notify_enrolled_users(
            capsule,
            title="Nouveau contenu bonus",
            message=message,
            link=link,
            exclude_user_ids={self.user.id},
        )

        return annotated_atoms

    def generate_and_save_plan(self, capsule_id: int, user_id: int):
        """
        Tâche de fond qui crée une roadmap personnelle pour un utilisateur en
        se basant sur la roadmap "modèle" de l'utilisateur système.
        """
        logger.info(f"\n--- [PLAN_GENERATOR] Tâche démarrée pour capsule ID: {capsule_id} et user ID: {user_id} ---")
        db: Session = SessionLocal()
        try:
            capsule = db.query(Capsule).get(capsule_id)
            user = db.query(User).get(user_id)
            if not capsule or not user:
                logger.error("Capsule ou Utilisateur non trouvé.")
                return

            # On vérifie si une roadmap existe déjà pour CET utilisateur
            if db.query(LanguageRoadmap).filter_by(capsule_id=capsule.id, user_id=user.id).first():
                logger.info("Une roadmap existe déjà pour cet utilisateur. Arrêt.")
                return

            # --- LOGIQUE DE COPIE CORRIGÉE ---
            # 1. Trouver l'utilisateur système et sa roadmap modèle
            system_user = db.query(User).filter(User.email == "system@nanshe.ai").first()
            if not system_user:
                raise ValueError("Utilisateur système 'system@nanshe.ai' introuvable.")

            template_roadmap = db.query(LanguageRoadmap).join(Capsule).filter(
                Capsule.main_skill == capsule.main_skill,
                LanguageRoadmap.user_id == system_user.id
            ).first()

            if not template_roadmap or not template_roadmap.roadmap_data:
                raise ValueError(f"Aucune roadmap modèle trouvée pour '{capsule.main_skill}'.")

            # 2. Créer la nouvelle roadmap pour l'utilisateur en copiant les données du modèle
            logger.info(f"Copie de la roadmap modèle pour l'utilisateur {user.id}...")
            new_roadmap = LanguageRoadmap(
                user_id=user.id,
                capsule_id=capsule.id,
                roadmap_data=template_roadmap.roadmap_data # On copie le plan JSON
            )
            db.add(new_roadmap)
            db.flush() # Pour obtenir l'ID de la nouvelle roadmap

            # 3. (Optionnel) Si vous voulez dénormaliser les niveaux, faites-le ici
            # C'est souvent plus simple de juste utiliser le JSON `roadmap_data` dans le frontend
            
            capsule.generation_status = GenerationStatus.COMPLETED
            db.commit()
            logger.info(f"-> ✅ SUCCÈS: Roadmap pour '{capsule.title}' créée pour l'utilisateur {user.id}.")
        
        except Exception as e:
            logger.error(f"-> ❌ ERREUR CRITIQUE lors de la génération du plan pour la capsule ID {capsule_id}: {e}", exc_info=True)
            if db.query(Capsule).get(capsule_id):
                db.rollback()
                capsule.generation_status = GenerationStatus.FAILED
                db.commit()
        finally:
            db.close()


    def _vectorize_skill(self, db: Session, capsule: Capsule):
        """Ajoute la compétence principale au VectorStore si elle n'y est pas déjà."""
        vector_exists = db.query(VectorStore).filter(VectorStore.skill == capsule.main_skill).first()
        if not vector_exists:
            logger.info(f"--- [VECTORIZER] Ajout de la compétence '{capsule.main_skill}' au VectorStore. ---")
            db.add(VectorStore(
                chunk_text=capsule.main_skill, 
                embedding=get_embedding(capsule.main_skill),
                domain=capsule.domain, 
                area=capsule.area, 
                skill=capsule.main_skill
            ))
            db.commit()

# ==============================================================================
# SECTION 3: FONCTIONS AUTONOMES (si nécessaire)
# ==============================================================================
# Cette fonction est maintenant indépendante de la classe, car elle est utilisée
# par le routeur pour la récupération de capsules.
def get_capsule_by_path(db: Session, user: User, domain: str, area: str, capsule_id: int) -> Capsule | None:
    """
    Récupère une capsule par son chemin et son ID, en vérifiant les permissions.
    """
    logger.info(f"--- [GET_BY_PATH] Recherche de la capsule ID:{capsule_id} via {domain}/{area} ---")
    
    capsule = db.query(Capsule).filter(
        Capsule.id == capsule_id,
        Capsule.domain == domain,
        # On pourrait aussi vérifier 'area' si c'est une contrainte stricte
        # Capsule.area == area 
    ).first()

    if not capsule:
        logger.warning(f"--- [GET_BY_PATH] Capsule ID {capsule_id} non trouvée.")
        return None

    # === LA CORRECTION EST ICI ===
    # L'appel au builder n'était pas nécessaire pour simplement afficher la capsule.
    # On le supprime. La fonction devient beaucoup plus simple.
    
    # Vérification des permissions : l'utilisateur peut-il voir cette capsule ?
    # (Ex: est-elle publique ou est-il le créateur ?)
    # Pour l'instant on la retourne si elle est publique.
    if not capsule.is_public and capsule.creator_id != user.id:
        logger.warning(f"--- [GET_BY_PATH] Accès refusé pour l'utilisateur {user.id} à la capsule {capsule_id}.")
        return None
    
    print("DIGIMON :: ", capsule)
    logger.info(f"--- [GET_BY_PATH] Capsule '{capsule.title}' trouvée et autorisée.")
    return capsule
